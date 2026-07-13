"""NL2SQL 评测 API 路由"""
from __future__ import annotations

from fastapi import APIRouter, Query
from app.evaluation.runner import EvalRunner, run_evaluation
from app.evaluation.dataset import EVAL_DATASET, list_categories, get_eval_case
from app.nl2sql.translator import NL2SQLTranslator
from app.evaluation.metrics import EvalSummary

evaluation_router: APIRouter = APIRouter(prefix="/api", tags=["evaluation"])

# 全局评测运行状态
_running: bool = False


@evaluation_router.get("/evaluation/cases")
async def list_cases() -> dict:
    """列出所有评测用例"""
    return {
        "total": len(EVAL_DATASET),
        "categories": list_categories(),
        "cases": [
            {
                "id": c.id,
                "question": c.question,
                "category": c.category,
                "description": c.description,
            }
            for c in EVAL_DATASET
        ],
    }


@evaluation_router.get("/evaluation/case/{case_id}")
async def get_case(case_id: str) -> dict:
    """获取单个评测用例详情"""
    case = get_eval_case(case_id)
    if not case:
        return {"error": f"评测用例 {case_id} 不存在"}
    return {
        "id": case.id,
        "question": case.question,
        "sql": case.sql,
        "description": case.description,
        "category": case.category,
    }


@evaluation_router.post("/evaluation/run")
async def run_eval(
    category: str | None = Query(None, description="按类别筛选"),
) -> dict:
    """运行 NL2SQL 评测"""
    global _running
    if _running:
        return {"error": "评测正在进行中，请稍后再试"}

    try:
        _running = True
        translator = NL2SQLTranslator()
        summary: EvalSummary = run_evaluation(
            category=category,
            translator=translator,
            use_llm_judge=True,
        )
        return {
            "total": summary.total,
            "valid_sql_count": summary.valid_sql_count,
            "execution_success_count": summary.execution_success_count,
            "exact_match_count": summary.exact_match_count,
            "avg_llm_score": summary.avg_llm_score,
            "category_breakdown": summary.category_breakdown,
            "results": [
                {
                    "case_id": r.case_id,
                    "question": r.question[:50],
                    "is_valid_sql": r.is_valid_sql,
                    "execution_success": r.execution_success,
                    "exact_set_match": r.exact_set_match,
                    "llm_score": r.llm_score,
                }
                for r in summary.results
            ],
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        _running = False
