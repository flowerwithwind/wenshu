"""
智能问数系统 - FastAPI 主入口
架构：NL2SQL 为主，RAG 为辅助
"""
from __future__ import annotations

import uuid
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from app.config import HOST, PORT, CORS_ORIGINS
from app.routes.chat import router as chat_router
from app.rag.pipeline import get_pipeline
from app.nl2sql.database import init_database, is_database_ready
from app.nl2sql.pipeline import get_nl2sql_pipeline
from app.middleware.rate_limit import check_rate_limit, build_rate_limit_response
from app.logging import get_logger, RequestIDFilter
from app.tracing import setup_tracing

logger = get_logger(__name__)

app: FastAPI = FastAPI(
    title="智能问数系统 API",
    description="基于 NL2SQL + RAG 架构的智能数据问答系统",
    version="2.0.0",
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
    except Exception:
        logger.warning(f"限流触发: {request.client.host if request.client else 'unknown'}")
        return JSONResponse(
            status_code=429,
            content=build_rate_limit_response(),
        )
    response: Response = await call_next(request)
    logger.info(f"{request.method} {request.url.path} - {response.status_code}")
    return response

# 注册路由
app.include_router(chat_router)
from app.routes.upload import upload_router
app.include_router(upload_router)
from app.routes.export import export_router
app.include_router(export_router)
from app.routes.knowledge import knowledge_router
app.include_router(knowledge_router)
from app.routes.analytics import analytics_router
app.include_router(analytics_router)
from app.routes.feedback import feedback_router
app.include_router(feedback_router)
from app.routes.evaluation import evaluation_router
app.include_router(evaluation_router)


@app.on_event("startup")
async def startup_event() -> None:
    """服务启动时初始化"""
    logger.info("=" * 50)
    logger.info("智能问数系统 v2.0.0 启动中...架构: NL2SQL 为主，RAG 为辅助")

    # 1. 初始化 SQLite 数据库
    logger.info("[1] 初始化 SQLite 数据库...")
    try:
        init_database()
        logger.info("数据库: 就绪")
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")

    # 2. 初始化 RAG 向量存储（辅助）
    logger.info("[2] 初始化 RAG 向量存储（辅助）...")
    try:
        pipeline = get_pipeline()
        stats = pipeline.get_stats()
        logger.info(f"向量存储: {'就绪' if stats['vector_store_ready'] else '未初始化'}")
        logger.info(f"文档块数: {stats['total_chunks']}")
    except Exception as e:
        logger.warning(f"RAG 启动警告: {e}")

    # 3. 初始化 NL2SQL Pipeline
    logger.info("[3] 初始化 NL2SQL Pipeline...")
    try:
        pipeline = get_pipeline()
        nl2sql = get_nl2sql_pipeline(rag_retriever=pipeline.retriever)
        nl2sql_stats = nl2sql.get_stats()
        logger.info(f"NL2SQL 翻译器: {'就绪' if nl2sql_stats['nl2sql_ready'] else '未配置'}")
        logger.info(f"SQLite 数据库: {'就绪' if nl2sql_stats['database_ready'] else '未初始化'}")
        logger.info(f"RAG 辅助: {'就绪' if nl2sql_stats['rag_ready'] else '未配置'}")
    except Exception as e:
        logger.warning(f"NL2SQL 启动警告: {e}")

    logger.info("启动完成")


@app.get("/")
async def root() -> dict[str, str]:
    """根路径"""
    return {
        "service": "智能问数系统",
        "version": "1.0.0",
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
