"""
NL2SQL 评估指标 — 多维度评测生成的 SQL 质量

评估维度:
1. 语法有效性 — 是否能被 SQLite 解析和执行
2. 执行准确率 — 执行结果是否与标准答案一致（行、列、值）
3. 精确集合匹配 — 结果集是否精确匹配标准结果
4. LLM-as-Judge — 大模型评估语义等价性（1-5 分）
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage

from app.models.provider import get_chat_model
from app.nl2sql.database import execute_sql
from app.logger import get_logger

logger = get_logger(__name__)


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


LLM_JUDGE_PROMPT: str = """你是一个 SQL 质量评审专家。比较"标准答案 SQL"和"待评估 SQL"，判断它们是否语义等价。

## 评判规则
1. 如果两者查询意图相同、结果集相同（列和行语义一致），打 5 分
2. 如果意图相同但实现方式略有差异（如列名别名不同、子查询 vs CTE），打 4 分
3. 如果意图基本一致但缺少部分条件或列（如漏了订单状态过滤），打 3 分
4. 如果意图部分正确但缺失关键条件，打 2 分
5. 如果完全错误或无法执行，打 1 分

## 输出格式
输出 JSON:
{{"score": 1-5, "reason": "简要说明"}}

## 评估
标准答案 SQL: {ground_truth}
待评估 SQL: {generated}
"""


def check_sql_validity(sql: str) -> bool:
    """检查 SQL 语法是否有效（能被 SQLite 解析）"""
    if not sql:
        return False
    upper = sql.strip().upper()
    if not upper.startswith("SELECT") and not upper.startswith("WITH"):
        return False
    return True


def evaluate_execution(sql: str) -> tuple[bool, list[dict[str, Any]], list[str], str]:
    """执行 SQL 并检查是否成功"""
    try:
        rows, columns = execute_sql(sql)
        return True, rows, columns, ""
    except Exception as e:
        return False, [], [], str(e)


def exact_set_match(
    generated_rows: list[dict[str, Any]],
    ground_truth_rows: list[dict[str, Any]],
) -> bool:
    """精确集合匹配（忽略列名差异，比较值集合）"""
    if len(generated_rows) != len(ground_truth_rows):
        return False

    # 排序后比较
    def _sort_key(row: dict[str, Any]) -> str:
        return json.dumps(sorted(row.items()), ensure_ascii=False)

    gen_sorted = sorted(
        [{k: v for k, v in r.items()} for r in generated_rows],
        key=_sort_key,
    )
    gt_sorted = sorted(
        [{k: v for k, v in r.items()} for r in ground_truth_rows],
        key=_sort_key,
    )

    return gen_sorted == gt_sorted


class LLMJudge:
    """LLM-as-Judge 评估器"""

    def __init__(self) -> None:
        self.llm: BaseChatModel = get_chat_model(temperature=0.0, max_tokens=512)

    def evaluate(
        self,
        ground_truth_sql: str,
        generated_sql: str,
    ) -> tuple[float, str]:
        """使用 LLM 评估 SQL 语义等价性"""
        prompt = LLM_JUDGE_PROMPT.format(
            ground_truth=ground_truth_sql,
            generated=generated_sql,
        )

        messages = [
            SystemMessage(content="你是一个专业的 SQL 评审专家。输出 JSON 格式评分结果。"),
            HumanMessage(content=prompt),
        ]

        try:
            response = self.llm.invoke(messages)
            text = response.content.strip()

            # 尝试从 markdown 代码块中提取 JSON
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


def run_single_evaluation(
    case_id: str,
    question: str,
    ground_truth_sql: str,
    generated_sql: str,
    llm_judge: LLMJudge | None = None,
) -> EvalResult:
    """对单个用例执行所有评估维度"""
    from time import time

    start = time()

    is_valid = check_sql_validity(generated_sql)

    # 执行生成的 SQL
    gen_success, gen_rows, gen_cols, gen_error = evaluate_execution(generated_sql)

    # 执行标准 SQL
    gt_success, gt_rows, gt_cols, gt_error = evaluate_execution(ground_truth_sql)

    execution_time = (time() - start) * 1000

    # 精确集合匹配（双方都执行成功时才比较）
    exact_match = None
    if gen_success and gt_success:
        exact_match = exact_set_match(gen_rows, gt_rows)
    elif not gen_success:
        exact_match = False

    # LLM-as-Judge 评估
    llm_score = None
    llm_judgment = ""
    if llm_judge is not None:
        llm_score, llm_judgment = llm_judge.evaluate(ground_truth_sql, generated_sql)

    return EvalResult(
        case_id=case_id,
        question=question,
        ground_truth_sql=ground_truth_sql,
        generated_sql=generated_sql,
        is_valid_sql=is_valid,
        execution_success=gen_success,
        execution_error=gen_error if not gen_success else "",
        exact_set_match=exact_match,
        llm_score=llm_score,
        llm_judgment=llm_judgment,
        execution_time_ms=round(execution_time, 2),
    )
