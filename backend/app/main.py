"""
智能问数系统 - FastAPI 主入口
架构：NL2SQL 为主，RAG 为辅助

推荐启动（在 backend 目录）:
    conda activate wenshu
    python -m app.main

也支持在 backend/app 下: python main.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# 将 backend/ 加入 sys.path，保证 `from app.xxx` 可解析
# （无论 cwd 是 backend 还是 backend/app）
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

import uuid
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from app.config import HOST, PORT, CORS_ORIGINS

# === 路由导入（统一在此处，避免散落注册） ===
from app.routes.chat import router as chat_router
from app.routes.upload import upload_router
from app.routes.export import export_router
from app.routes.knowledge import knowledge_router
from app.routes.analytics import analytics_router
from app.routes.feedback import feedback_router
from app.routes.evaluation import evaluation_router
from app.routes.evaluation_v2 import router as evaluation_v2_router
from app.routes.models import models_router
from app.routes.datasource import datasource_router
from app.routes.auth import auth_router

# === 核心模块 ===
from app.rag.pipeline import get_pipeline
from app.nl2sql.database import init_database
from app.nl2sql.pipeline import get_nl2sql_pipeline
from app.auth.models import init_auth_db
from app.middleware.rate_limit import (
    check_rate_limit,
    build_rate_limit_response,
    RateLimitExceededError,
)
from app.logger import get_logger, RequestIDFilter
from app.tracing import setup_tracing

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """应用生命周期：启动初始化 + 关闭清理"""
    logger.info("=" * 50)
    logger.info("智能问数系统 v2.0.0 启动中...架构: NL2SQL 为主，RAG 为辅助")

    logger.info("[1] 初始化 SQLite 数据库...")
    try:
        init_database()
        logger.info("数据库: 就绪")
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")

    logger.info("[1.5] 初始化认证数据库...")
    try:
        init_auth_db()
    except Exception as e:
        logger.error(f"认证数据库初始化失败: {e}")

    logger.info("[2] 初始化 RAG 向量存储（辅助）...")
    pipeline = None
    try:
        pipeline = get_pipeline()
        stats = pipeline.get_stats()
        ready = bool(stats.get("vector_store_ready"))
        logger.info(f"向量存储: {'就绪' if ready else '未初始化/已降级'}")
        logger.info(f"文档块数: {stats.get('total_chunks', 0)}")
        if not ready:
            logger.warning(
                "RAG 索引不可用：NL2SQL 主路径仍可用。"
                "重建: POST /api/rebuild-index 或删除 data/chroma_db 后重建"
            )
    except Exception as e:
        logger.warning(f"RAG 启动警告（已降级）: {e}")

    logger.info("[3] 初始化 NL2SQL Pipeline...")
    try:
        if pipeline is None:
            pipeline = get_pipeline()
        retriever = pipeline.retriever if pipeline is not None else None
        nl2sql = get_nl2sql_pipeline(rag_retriever=retriever)
        nl2sql_stats = nl2sql.get_stats()
        logger.info(f"NL2SQL 翻译器: {'就绪' if nl2sql_stats['nl2sql_ready'] else '未配置'}")
        logger.info(f"SQLite 数据库: {'就绪' if nl2sql_stats['database_ready'] else '未初始化'}")
        logger.info(
            f"RAG 辅助: {'就绪' if nl2sql_stats['rag_ready'] else '未就绪（索引缺失/损坏）'}"
        )
    except Exception as e:
        logger.warning(f"NL2SQL 启动警告: {e}")

    logger.info("启动完成")
    yield
    logger.info("服务关闭")


app: FastAPI = FastAPI(
    title="智能问数系统 API",
    description="基于 NL2SQL + RAG 架构的智能数据问答系统",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OpenTelemetry 链路追踪
setup_tracing(app)

# 请求 ID 注入 + 限流中间件
@app.middleware("http")
async def request_context_middleware(request: Request, call_next) -> Response:
    request_id: str = request.headers.get("X-Request-ID", uuid.uuid4().hex[:12])
    RequestIDFilter.set_request_id(request_id)
    logger.info(f"{request.method} {request.url.path} - 请求开始")
    try:
        await check_rate_limit(request)
    except RateLimitExceededError as e:
        logger.warning(f"限流触发: {request.client.host if request.client else 'unknown'}")
        return JSONResponse(
            status_code=429,
            content=build_rate_limit_response(),
        )
    response: Response = await call_next(request)
    logger.info(f"{request.method} {request.url.path} - {response.status_code}")
    return response


# === 路由统一注册 ===
_ALL_ROUTERS = [
    chat_router,
    upload_router,
    export_router,
    knowledge_router,
    analytics_router,
    feedback_router,
    evaluation_router,
    evaluation_v2_router,
    models_router,
    datasource_router,
    auth_router,
]
for _router in _ALL_ROUTERS:
    app.include_router(_router)


@app.get("/")
async def root() -> dict[str, str]:
    """根路径"""
    return {
        "service": "智能问数系统",
        "version": "2.0.0",
        "docs": "/docs",
    }


# 启动入口
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=HOST,
        port=PORT,
        reload=True,
    )
