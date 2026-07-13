"""数据看板 API 路由"""
from __future__ import annotations

from fastapi import APIRouter
from app.services.analytics import get_overview_stats

analytics_router: APIRouter = APIRouter(prefix="/api", tags=["analytics"])


@analytics_router.get("/dashboard/overview")
async def dashboard_overview() -> dict:
    """看板概览数据"""
    return get_overview_stats()
