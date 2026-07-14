"""
NL2SQL 评估运行器 — 批量评测 NL2SQL Pipeline 的 SQL 生成质量

流程:
1. 加载评测数据集
2. 对每个用例: 调用 pipeline.translate() → 收集 SQL → 执行评估指标
3. 汇总结果: 按类别统计准确率、LLM分数等
"""
from __future__ import annotations

import time
from typing import Any

from app.evaluation.dataset import EVAL_DATASET, get_cases_by_category, EvalCase
from app.evaluation.metrics import (
    EvalResult,
    EvalSummary,
    LLMJudge,
    check_sql_validity,
    evaluate_execution,
    exact_set_match,
    run_single_evaluation,
)
from app.nl2sql.translator import NL2SQLTranslator
from app.nl2sql.database import get_schema_info
from app.logger import get_logger

logger = get_logger(__name__)


class EvalRunner:
    """NL2SQL 评测运行器"""

    def __init__(
        self,
        translator: NL2SQLTranslator | None = None,
        use_llm_judge: bool = True,
    ) -> None:
        self.translator = translator
        self.use_llm_judge = use_llm_judge
        self.llm_judge: LLMJudge | None = LLMJudge() if use_llm_judge else None

    def run_all(self) -> EvalSummary:
        """运行全部评测用例"""
        logger.info(f"开始 NL2SQL 评测: {len(EVAL_DATASET)} 个用例")
        return self._run_cases(EVAL_DATASET)

    def run_category(self, category: str) -> EvalSummary:
        """按类别运行评测"""
        cases = get_cases_by_category(category)
        logger.info(f"开始 NL2SQL 评测({category}): {len(cases)} 个用例")
        return self._run_cases(cases)

    def _run_cases(self, cases: list[EvalCase]) -> EvalSummary:
        """执行一系列评测用例"""
        if not self.translator:
            raise RuntimeError("NL2SQLTranslator 未初始化")

        schema = get_schema_info()
        results: list[EvalResult] = []
        category_stats: dict[str, dict[str, float]] = {}

        for case in cases:
            logger.info(f"评测 [{case.id}] {case.question[:40]}...")

            # Step 1: 翻译 SQL
            try:
                generated_sql = self.translator.translate(
                    question=case.question,
                    schema=schema,
                )
            except Exception as e:
                generated_sql = ""
                logger.warning(f"[{case.id}] 翻译失败: {e}")

            # Step 2: 多维度评估
            result = run_single_evaluation(
                case_id=case.id,
                question=case.question,
                ground_truth_sql=case.sql,
                generated_sql=generated_sql,
                llm_judge=self.llm_judge,
            )
            results.append(result)

            # 累加类别统计
            cat = case.category
            if cat not in category_stats:
                category_stats[cat] = {"total": 0, "exec_ok": 0, "exact_ok": 0, "llm_sum": 0.0}
            category_stats[cat]["total"] += 1
            if result.execution_success:
                category_stats[cat]["exec_ok"] += 1
            if result.exact_set_match:
                category_stats[cat]["exact_ok"] += 1
            if result.llm_score is not None:
                category_stats[cat]["llm_sum"] += result.llm_score

            logger.info(
                f"  → 有效={result.is_valid_sql}, "
                f"执行={'✓' if result.execution_success else '✗'}, "
                f"精确={'✓' if result.exact_set_match else '✗' if result.exact_set_match is not None else '-'}, "
                f"LLM={result.llm_score}" if result.llm_score else ""
            )

        # 构建汇总
        total = len(results)
        valid_sql_count = sum(1 for r in results if r.is_valid_sql)
        exec_ok_count = sum(1 for r in results if r.execution_success)
        exact_ok_count = sum(1 for r in results if r.exact_set_match)
        llm_scores = [r.llm_score for r in results if r.llm_score is not None]

        category_breakdown = {}
        for cat, stats in category_stats.items():
            t = stats["total"]
            category_breakdown[cat] = {
                "count": t,
                "execution_accuracy": round(stats["exec_ok"] / t * 100, 1) if t else 0.0,
                "exact_match_rate": round(stats["exact_ok"] / t * 100, 1) if t else 0.0,
                "avg_llm_score": round(stats["llm_sum"] / t, 2) if t else 0.0,
            }

        summary = EvalSummary(
            total=total,
            valid_sql_count=valid_sql_count,
            execution_success_count=exec_ok_count,
            exact_match_count=exact_ok_count,
            avg_llm_score=round(sum(llm_scores) / len(llm_scores), 2) if llm_scores else 0.0,
            results=results,
            category_breakdown=category_breakdown,
        )

        self._log_summary(summary)
        return summary

    def _log_summary(self, summary: EvalSummary) -> None:
        """打印评测汇总"""
        total = summary.total
        lines = [
            "\n===== NL2SQL 评测报告 =====",
            f"总用例: {total}",
            f"语法有效: {summary.valid_sql_count}/{total} ({summary.valid_sql_count / total * 100:.1f}%)" if total else "",
            f"执行成功: {summary.execution_success_count}/{total} ({summary.execution_success_count / total * 100:.1f}%)" if total else "",
            f"精确匹配: {summary.exact_match_count}/{total} ({summary.exact_match_count / total * 100:.1f}%)" if total else "",
            f"LLM 平均分: {summary.avg_llm_score}/5.0" if summary.avg_llm_score else "",
        ]
        if summary.category_breakdown:
            lines.append("\n-- 按类别 --")
            for cat, stats in summary.category_breakdown.items():
                lines.append(
                    f"  {cat}: 执行={stats['execution_accuracy']}% "
                    f"精确={stats['exact_match_rate']}% "
                    f"LLM={stats['avg_llm_score']}/5.0"
                )
        logger.info("\n".join(filter(None, lines)))


def run_evaluation(
    category: str | None = None,
    translator: NL2SQLTranslator | None = None,
    use_llm_judge: bool = True,
) -> EvalSummary:
    """快捷入口：运行 NL2SQL 评测"""
    runner = EvalRunner(translator=translator, use_llm_judge=use_llm_judge)
    if category:
        return runner.run_category(category)
    return runner.run_all()
