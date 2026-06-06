"""
智能问数系统 - FastAPI 主入口
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles
from app.config import HOST, PORT, CORS_ORIGINS
from app.routes.chat import router as chat_router
from app.rag.pipeline import get_pipeline

app = FastAPI(
    title="智能问数系统 API",
    description="基于 LangChain + RAG 架构的智能数据问答系统",
    version="1.0.0",
)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(chat_router)


@app.on_event("startup")
async def startup_event():
    """服务启动时初始化"""
    print("=" * 50)
    print("  智能问数系统 v1.0.0 启动中...")
    print("=" * 50)
    try:
        pipeline = get_pipeline()
        stats = pipeline.get_stats()
        print(f"  向量存储: {'就绪' if stats['vector_store_ready'] else '未初始化'}")
        print(f"  模型状态: {'就绪' if stats['model_ready'] else '未配置'}")
        print(f"  文档块数: {stats['total_chunks']}")
    except Exception as e:
        print(f"  启动警告: {e}")
    print("=" * 50)


@app.get("/")
async def root():
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