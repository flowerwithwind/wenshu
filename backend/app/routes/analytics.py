"""数据看板 API 路由"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.services.analytics import get_overview_stats

analytics_router: APIRouter = APIRouter(prefix="/api", tags=["analytics"])


@analytics_router.get("/dashboard/overview")
async def dashboard_overview(
    datasource_id: str | None = Query(
        default=None,
        description="数据源 ID；省略则使用默认数据源",
    ),
) -> dict[str, Any]:
    """看板概览数据（支持切换数据源）"""
    return get_overview_stats(datasource_id)
