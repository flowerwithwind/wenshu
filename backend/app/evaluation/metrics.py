"""
评估指标 - 包含新旧两套 API（向后兼容）
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage

from app.models.provider import get_chat_model
from app.nl2sql.database import execute_sql
from app.logger import get_logger

logger = get_logger(__name__)


# ==================== 旧 API（NL2SQL 评估）====================

@dataclass
class EvalResult:
    """单个评测用例的结果"""
    case_id: str
    question: str
    ground_truth_sql: str
    generated_sql: str
    is_valid_sql: bool
    execution_success: bool
    execution_error: str = ""
    exact_set_match: bool | None = None
    llm_score: float | None = None
    llm_judgment: str = ""
    execution_time_ms: float = 0.0


@dataclass
class EvalSummary:
    """评测汇总"""
    total: int = 0
    valid_sql_count: int = 0
    execution_success_count: int = 0
    exact_match_count: int = 0
    avg_llm_score: float = 0.0
    results: list[EvalResult] = field(default_factory=list)
    category_breakdown: dict[str, dict[str, float]] = field(default_factory=dict)


def check_sql_validity(sql: str) -> bool:
    """检查 SQL 语法是否有效"""
    if not sql:
        return False
    upper = sql.strip().upper()
    return upper.startswith("SELECT") or upper.startswith("WITH")


def evaluate_execution(sql: str) -> tuple[bool, list[dict[str, Any]], list[str], str]:
    """执行 SQL 并检查是否成功"""
    try:
        rows, columns = execute_sql(sql)
        return True, rows, columns, ""
    except Exception as e:
        return False, [], [], str(e)


def exact_set_match(generated_rows: list[dict[str, Any]], ground_truth_rows: list[dict[str, Any]]) -> bool:
    """精确集合匹配"""
    if len(generated_rows) != len(ground_truth_rows):
        return False

    def sort_key(row: dict[str, Any]) -> str:
        return json.dumps(sorted(row.items()), ensure_ascii=False)

    gen_sorted = sorted([{k: v for k, v in r.items()} for r in generated_rows], key=sort_key)
    gt_sorted = sorted([{k: v for k, v in r.items()} for r in ground_truth_rows], key=sort_key)
    return gen_sorted == gt_sorted


class LLMJudge:
    """LLM-as-Judge 评估器"""
    def __init__(self) -> None:
        self.llm: BaseChatModel = get_chat_model(temperature=0.0, max_tokens=512)

    def evaluate(self, ground_truth_sql: str, generated_sql: str) -> tuple[float, str]:
        prompt = LLM_JUDGE_PROMPT.format(ground_truth=ground_truth_sql, generated=generated_sql)
        messages = [SystemMessage(content="你是一个专业的 SQL 评审专家。输出 JSON 格式评分结果。"), HumanMessage(content=prompt)]
        try:
            response = self.llm.invoke(messages)
            text = response.content.strip()
            import re
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
            if json_match:
                text = json_match.group(1)
            result = json.loads(text)
            score = float(result.get("score", 1))
            reason = result.get("reason", "")
            return min(max(score, 1.0), 5.0), reason
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"LLM Judge 解析失败: {e}")
            return 1.0, f"评分解析错误: {e}"


def run_single_evaluation(case_id: str, question: str, ground_truth_sql: str, generated_sql: str, llm_judge: LLMJudge | None = None) -> EvalResult:
    from time import time
    start = time()
    is_valid = check_sql_validity(generated_sql)
    gen_success, gen_rows, gen_cols, gen_error = evaluate_execution(generated_sql)
    gt_success, gt_rows, gt_cols, gt_error = evaluate_execution(ground_truth_sql)
    execution_time = (time() - start) * 1000
    exact_match = None
    if gen_success and gt_success:
        exact_match = exact_set_match(gen_rows, gt_rows)
    elif not gen_success:
        exact_match = False
    llm_score = None
    llm_judgment = ""
    if llm_judge is not None:
        llm_score, llm_judgment = llm_judge.evaluate(ground_truth_sql, generated_sql)
    return EvalResult(case_id=case_id, question=question, ground_truth_sql=ground_truth_sql, generated_sql=generated_sql, is_valid_sql=is_valid, execution_success=gen_success, execution_error=gen_error if not gen_success else "", exact_set_match=exact_match, llm_score=llm_score, llm_judgment=llm_judgment, execution_time_ms=round(execution_time, 2))


LLM_JUDGE_PROMPT: str = """你是一个 SQL 质量评审专家。比较"标准答案 SQL"和"待评估 SQL"，判断它们是否语义等价。

## 评判规则
1. 如果两者查询意图相同、结果集相同，打 5 分
2. 如果意图相同但实现方式略有差异，打 4 分
3. 如果意图基本一致但缺少部分条件或列，打 3 分
4. 如果意图部分正确但缺失关键条件，打 2 分
5. 如果完全错误或无法执行，打 1 分

## 输出格式
输出 JSON: {{"score": 1-5, "reason": "简要说明"}}

## 评估
标准答案 SQL: {ground_truth}
待评估 SQL: {generated}
"""


# ==================== 新 API（检索评估指标）====================

def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    return len(set(retrieved[:k]) & relevant) / len(relevant)


def precision_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    if k == 0:
        return 0.0
    return len(set(retrieved[:k]) & relevant) / k


def mrr(retrieved: list[str], relevant: set[str]) -> float:
    for i, doc_id in enumerate(retrieved):
        if doc_id in relevant:
            return 1.0 / (i + 1)
    return 0.0


def ndcg_at_k(retrieved, relevant, graded_relevance=None, k=4):
    """NDCG@K：理想序基于相关文档集合（而非仅 retrieved 列表）。"""
    if not relevant or k <= 0:
        return 0.0
    if graded_relevance:
        actual = [float(graded_relevance.get(d, 0.0)) for d in retrieved[:k]]
        ideal_scores = sorted(
            (float(graded_relevance.get(d, 0.0)) for d in relevant),
            reverse=True,
        )[:k]
    else:
        actual = [1.0 if d in relevant else 0.0 for d in retrieved[:k]]
        ideal_scores = [1.0] * min(len(relevant), k)

    def dcg(scores: list[float]) -> float:
        return sum(s / math.log2(i + 2) for i, s in enumerate(scores))

    idcg = dcg(ideal_scores)
    return dcg(actual) / idcg if idcg > 0 else 0.0


class MetricsCalculator:
    @staticmethod
    def evaluate(retrieved, relevant, k_values=None):
        if k_values is None:
            k_values = [1, 3, 5]
        return {
            **{f"recall@{k}": round(recall_at_k(retrieved, relevant, k), 4) for k in k_values},
            **{f"precision@{k}": round(precision_at_k(retrieved, relevant, k), 4) for k in k_values},
            **{f"ndcg@{k}": round(ndcg_at_k(retrieved, relevant, k=k), 4) for k in k_values},
            "mrr": round(mrr(retrieved, relevant), 4),
        }
