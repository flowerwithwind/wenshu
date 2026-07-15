"""
评估子系统
"""
from __future__ import annotations

from app.evaluation.dataset import EVAL_DATASET, EvalCase, get_eval_case, get_cases_by_category, list_categories
from app.evaluation.metrics import EvalResult, EvalSummary, LLMJudge, MetricsCalculator, check_sql_validity, evaluate_execution, exact_set_match, run_single_evaluation, recall_at_k, precision_at_k, mrr, ndcg_at_k
from app.evaluation.runner import EvalRunner, EvaluationRunner, run_evaluation

__all__ = [
    "EVAL_DATASET", "EvalCase", "get_eval_case", "get_cases_by_category", "list_categories",
    "EvalResult", "EvalSummary", "LLMJudge", "MetricsCalculator",
    "check_sql_validity", "evaluate_execution", "exact_set_match", "run_single_evaluation",
    "recall_at_k", "precision_at_k", "mrr", "ndcg_at_k",
    "EvalRunner", "EvaluationRunner", "run_evaluation",
]
