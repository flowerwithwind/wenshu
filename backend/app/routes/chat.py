"""
聊天 API 路由 - NL2SQL 为主，RAG 为辅助
"""
from __future__ import annotations

import uuid
import json
import re
from typing import AsyncGenerator
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    DatasetInfo,
    HealthResponse,
    SQLResult,
    ErrorResponse,
)
from app.rag.pipeline import get_pipeline
from app.nl2sql.database import init_database, is_database_ready
from app.nl2sql.pipeline import get_nl2sql_pipeline
from app.exceptions import ErrorCode, ERROR_MESSAGES, HTTP_STATUS_MAP, classify_exception
from app.services.conversation_store import get_conversation_store
from app.logging import get_logger

logger = get_logger(__name__)

router: APIRouter = APIRouter(prefix="/api", tags=["chat"])


def _build_error_response(e: Exception) -> tuple[int, ErrorResponse]:
    """构建统一的错误响应，返回 (status_code, ErrorResponse)"""
    error_code: ErrorCode = classify_exception(e)
    status_code: int = HTTP_STATUS_MAP.get(error_code, 500)
    detail: str = str(e)[:200]  # 截断到 200 字符，防止敏感信息泄露
    return status_code, ErrorResponse(
        error_code=error_code.value,
        message=ERROR_MESSAGES[error_code],
        detail=detail,
    )


def _serialize_sources(sources: list) -> list[dict]:
    """将 SourceDocument 列表序列化为可 JSON 化的字典列表"""
    result: list[dict] = []
    for s in sources:
        if hasattr(s, 'content'):
            result.append({
                "content": s.content,
                "source": s.source,
                "score": s.score,
                "metadata": s.metadata,
            })
        elif isinstance(s, dict):
            result.append(s)
    return result


def _get_nl2sql_pipeline():
    """获取 NL2SQL Pipeline，并注入 RAG 检索器"""
    rag = get_pipeline()
    return get_nl2sql_pipeline(rag_retriever=rag.retriever)


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """健康检查接口"""
    pipeline = get_pipeline()
    stats = pipeline.get_stats()
    nl2sql = _get_nl2sql_pipeline()
    nl2sql_stats = nl2sql.get_stats()
    return HealthResponse(
        status="ok",
        version="1.0.0",
        model="deepseek-chat (NL2SQL)" if nl2sql_stats["nl2sql_ready"] else "未配置",
        vector_store=f"就绪 ({stats['total_chunks']} 块)"
        if stats["vector_store_ready"]
        else "未初始化",
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """聊天接口 - NL2SQL 非流式"""
    try:
        nl2sql = _get_nl2sql_pipeline()
        result = nl2sql.query(
            question=request.question,
            conversation_id=request.conversation_id,
        )

        # 保存对话历史
        conv_id: str = result["conversation_id"]
        store = get_conversation_store()
        store.add_message(conv_id, {
            "id": result["id"],
            "question": request.question,
            "answer": result["answer"],
            "sql": result.get("sql", ""),
            "sql_result": result.get("sql_result"),
            "sources": [
                {"content": s.content, "source": s.source, "score": s.score, "metadata": s.metadata}
                for s in (result.get("sources") or [])
            ],
            "created_at": result["created_at"],
        })

        # 构建 SQLResult
        sql_result: SQLResult | None = None
        if result.get("sql_result"):
            sql_result = SQLResult(**result["sql_result"])

        return ChatResponse(
            id=result["id"],
            question=result["question"],
            answer=result["answer"],
            sources=result.get("sources", []),
            conversation_id=result["conversation_id"],
            created_at=result["created_at"],
            response_time_ms=result["response_time_ms"],
            has_numeric_data=result["has_numeric_data"],
            chart_data=result.get("chart_data"),
            sql=result.get("sql"),
            sql_result=sql_result,
        )
    except Exception as e:
        status_code, error_response = _build_error_response(e)
        raise HTTPException(status_code=status_code, detail=error_response.model_dump())


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    """聊天接口 - NL2SQL 流式输出"""
    nl2sql = _get_nl2sql_pipeline()

    async def generate() -> AsyncGenerator[str, None]:
        try:
            full_answer: str = ""
            for chunk in nl2sql.query_stream(request.question, request.conversation_id):
                full_answer += chunk
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"

            conv_id: str = request.conversation_id or str(uuid.uuid4())
            store = get_conversation_store()
            store.add_message(conv_id, {
                "id": str(uuid.uuid4()),
                "question": request.question,
                "answer": full_answer,
                "sql": getattr(nl2sql, '_last_sql', ''),
                "sql_result": getattr(nl2sql, '_last_sql_result', None),
                "sources": [
                    {"content": s.content, "source": s.source, "score": s.score, "metadata": s.metadata}
                    for s in getattr(nl2sql, '_last_sources', [])
                ],
                "created_at": "",
            })

            yield f"data: {json.dumps({'done': True, 'conversation_id': conv_id, 'sources': _serialize_sources(getattr(nl2sql, '_last_sources', [])), 'sql': getattr(nl2sql, '_last_sql', ''), 'sql_result': getattr(nl2sql, '_last_sql_result', None), 'response_time_ms': getattr(nl2sql, '_last_response_time_ms', 0), 'chart_data': getattr(nl2sql, '_last_chart_data', None), 'has_numeric_data': getattr(nl2sql, '_last_has_numeric_data', False)})}\n\n"

            # 生成推荐问题
            from app.nl2sql.translator import RecommendedQuestionsGenerator
            from app.nl2sql.database import get_schema_info
            try:
                rec_gen: RecommendedQuestionsGenerator = RecommendedQuestionsGenerator()
                schema: str = get_schema_info()
                # 清理回答中的 chart_data 标记
                clean_answer: str = re.sub(r'```chart_data\s*\n.*?\n```', '', full_answer, flags=re.DOTALL)
                recommended: list[str] = rec_gen.generate(request.question, clean_answer, schema)
                if recommended:
                    yield f"data: {json.dumps({'recommended_questions': recommended})}\n\n"
            except Exception as e:
                logger.warning(f"推荐问题生成失败: {e}")
        except Exception as e:
            status_code, error_response = _build_error_response(e)
            yield f"data: {json.dumps({'error': error_response.model_dump()})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.post("/chat/agent", response_model=ChatResponse)
async def chat_agent(request: ChatRequest) -> ChatResponse:
    try:
        nl2sql = _get_nl2sql_pipeline()
        result = nl2sql.query_agent(
            question=request.question,
            conversation_id=request.conversation_id,
        )
        conv_id: str = result["conversation_id"]
        store = get_conversation_store()
        store.add_message(conv_id, {
            "id": result["id"],
            "question": request.question,
            "answer": result["answer"],
            "sql": result.get("sql", ""),
            "sql_result": result.get("sql_result"),
            "sources": [
                {"content": s.content, "source": s.source, "score": s.score, "metadata": s.metadata}
                for s in (result.get("sources") or [])
            ],
            "created_at": result["created_at"],
        })
        sql_result: SQLResult | None = None
        if result.get("sql_result"):
            sql_result = SQLResult(**result["sql_result"])
        return ChatResponse(
            id=result["id"],
            question=result["question"],
            answer=result["answer"],
            sources=result.get("sources", []),
            conversation_id=result["conversation_id"],
            created_at=result["created_at"],
            response_time_ms=result["response_time_ms"],
            has_numeric_data=result.get("has_numeric_data", result.get("chart_data") is not None),
            chart_data=result.get("chart_data"),
            sql=result.get("sql"),
            sql_result=sql_result,
        )
    except Exception as e:
        status_code, error_response = _build_error_response(e)
        raise HTTPException(status_code=status_code, detail=error_response.model_dump())


@router.post("/chat/agent/stream")
async def chat_agent_stream(request: ChatRequest) -> StreamingResponse:
    nl2sql = _get_nl2sql_pipeline()

    async def generate() -> AsyncGenerator[str, None]:
        try:
            full_answer: str = ""
            conv_id: str = request.conversation_id or str(uuid.uuid4())
            for event_str in nl2sql.query_agent_stream(request.question, conv_id):
                yield f"data: {event_str}\n\n"
                event = json.loads(event_str)
                if event.get("type") == "done":
                    full_answer = event.get("answer", "")
            store = get_conversation_store()
            store.add_message(conv_id, {
                "id": str(uuid.uuid4()),
                "question": request.question,
                "answer": full_answer,
                "sql": "",
                "sql_result": None,
                "sources": [],
                "created_at": "",
            })
        except Exception as e:
            status_code, error_response = _build_error_response(e)
            yield f"data: {json.dumps({'error': error_response.model_dump()})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.get("/history")
async def get_history() -> dict:
    """获取所有对话历史"""
    store = get_conversation_store()
    history = store.list_all()
    return {"conversations": history}


@router.get("/history/{conversation_id}")
async def get_conversation(conversation_id: str) -> dict:
    """获取指定对话的详细内容"""
    store = get_conversation_store()
    conv = store.get(conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="对话不存在")
    return conv


@router.delete("/history/{conversation_id}")
async def delete_conversation(conversation_id: str) -> dict:
    """删除指定对话"""
    store = get_conversation_store()
    if store.delete(conversation_id):
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="对话不存在")


@router.post("/rebuild-index")
async def rebuild_index() -> dict:
    """重建向量索引"""
    try:
        pipeline = get_pipeline()
        count: int = pipeline.build_index()
        return {"status": "ok", "chunks_created": count}
    except Exception as e:
        status_code, error_response = _build_error_response(e)
        raise HTTPException(status_code=status_code, detail=error_response.model_dump())


@router.get("/dataset-info", response_model=DatasetInfo)
async def get_dataset_info() -> DatasetInfo:
    """获取数据集信息"""
    pipeline = get_pipeline()
    stats = pipeline.get_stats()
    return DatasetInfo(
        name="知识库",
        file_count=0,
        total_chunks=stats["total_chunks"],
        last_updated=None,
    )
