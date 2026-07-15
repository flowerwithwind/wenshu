"""
评估 V2 API - 检索策略对比评测
"""
from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.evaluation.benchmark import BenchmarkLoader
from app.evaluation.runner import EvaluationRunner
from app.rag.pipeline import get_pipeline

# 使用独立前缀，避免与 NL2SQL 评测路由 POST /api/evaluation/run 冲突
router = APIRouter(prefix="/api/evaluation/retrieval", tags=["evaluation-retrieval"])

benchmark = BenchmarkLoader()
runner: EvaluationRunner | None = None


def _get_runner() -> EvaluationRunner:
    global runner
    if runner is None:
        pipeline = get_pipeline()
        runner = EvaluationRunner(pipeline)
    return runner


@router.get("/stats")
async def get_stats() -> dict[str, Any]:
    """评测集概况"""
    items = benchmark.load()
    categories: dict[str, int] = {}
    for item in items:
        cat = item.category
        categories[cat] = categories.get(cat, 0) + 1

    return {
        "total": len(items),
        "categories": categories,
        "is_loaded": len(items) > 0,
    }


@router.post("/run")
async def run_evaluation(
    strategies: list[str] | None = None,
) -> dict[str, Any]:
    """执行完整评测"""
    r = _get_runner()
    try:
        result = r.run_all(strategies=strategies)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/results/{eval_id}")
async def get_result(eval_id: str) -> dict[str, str]:
    """获取历史评测结果（暂未持久化）"""
    return {
        "message": f"评测 {eval_id} 结果未持久化，请重新运行评测",
        "eval_id": eval_id,
    }


@router.get("/strategies")
async def list_strategies() -> dict[str, list[dict[str, str]]]:
    """列出可用检索策略"""
    return {
        "strategies": [
            {"id": "semantic", "name": "纯语义检索", "description": "ChromaDB cosine similarity"},
            {"id": "bm25", "name": "BM25关键词检索", "description": "基于 rank_bm25 的精确匹配"},
            {"id": "hybrid", "name": "混合检索", "description": "语义+BM25 加权融合 (alpha=0.7)"},
            {"id": "hybrid_reranked", "name": "混合检索+精排", "description": "混合检索 + Cross-encoder 重排序"},
        ]
    }
