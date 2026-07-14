"""
聊天 API 路由 - NL2SQL 为主，RAG 为辅助
"""
from __future__ import annotations

import time
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
from app.logger import get_logger

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
                "metadata": s.metadata if isinstance(getattr(s, "metadata", None), dict) else {},
            })
        elif isinstance(s, dict):
            result.append(s)
    return result


def _sse_data(payload: dict) -> str:
    """安全序列化 SSE data 行（避免不可 JSON 化对象导致流中断）"""
    return f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"


def _get_nl2sql_pipeline():
    """获取 NL2SQL Pipeline，并注入 RAG 检索器"""
    rag = get_pipeline()
    return get_nl2sql_pipeline(rag_retriever=rag.retriever)


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """健康检查接口"""
    from app.models.provider import get_provider_status

    pipeline = get_pipeline()
    stats = pipeline.get_stats()
    nl2sql = _get_nl2sql_pipeline()
    nl2sql_stats = nl2sql.get_stats()
    prov = get_provider_status()
    model_label = f"{prov['label']} / {prov['model']}"
    if not nl2sql_stats["nl2sql_ready"]:
        model_label = "未配置"
    return HealthResponse(
        status="ok",
        version="2.0.0",
        model=model_label,
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
            datasource_id=request.datasource_id,
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
            "chart_data": result.get("chart_data"),
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
    """聊天接口 - NL2SQL 流式输出（message_id 由服务端生成并回传）"""
    import asyncio

    nl2sql = _get_nl2sql_pipeline()

    async def generate() -> AsyncGenerator[str, None]:
        try:
            full_answer: str = ""
            conv_id: str = request.conversation_id or str(uuid.uuid4())
            # 同步 generator 会阻塞事件循环；每 yield 后 sleep(0) 让出控制权以便刷出 SSE
            for chunk in nl2sql.query_stream(
                request.question, conv_id, request.datasource_id,
            ):
                full_answer += chunk
                yield _sse_data({"chunk": chunk})
                await asyncio.sleep(0)

            message_id: str = getattr(nl2sql, "_last_message_id", "") or str(uuid.uuid4())
            store = get_conversation_store()
            sources_serialized = _serialize_sources(getattr(nl2sql, "_last_sources", []))
            store.add_message(conv_id, {
                "id": message_id,
                "question": request.question,
                "answer": full_answer,
                "sql": getattr(nl2sql, "_last_sql", ""),
                "sql_result": getattr(nl2sql, "_last_sql_result", None),
                "sources": sources_serialized,
                "chart_data": getattr(nl2sql, "_last_chart_data", None),
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            })

            yield _sse_data({
                "done": True,
                "message_id": message_id,
                "conversation_id": conv_id,
                "sources": sources_serialized,
                "sql": getattr(nl2sql, "_last_sql", ""),
                "sql_result": getattr(nl2sql, "_last_sql_result", None),
                "response_time_ms": getattr(nl2sql, "_last_response_time_ms", 0),
                "chart_data": getattr(nl2sql, "_last_chart_data", None),
                "has_numeric_data": getattr(nl2sql, "_last_has_numeric_data", False),
            })
            await asyncio.sleep(0)

            from app.nl2sql.translator import RecommendedQuestionsGenerator
            from app.nl2sql.database import get_schema_info
            try:
                rec_gen: RecommendedQuestionsGenerator = RecommendedQuestionsGenerator()
                schema: str = get_schema_info()
                clean_answer: str = re.sub(r'```chart_data\s*\n.*?\n```', '', full_answer, flags=re.DOTALL)
                recommended: list[str] = rec_gen.generate(request.question, clean_answer, schema)
                if recommended:
                    yield _sse_data({"recommended_questions": recommended})
                    await asyncio.sleep(0)
            except Exception as e:
                logger.warning(f"推荐问题生成失败: {e}")
        except Exception as e:
            status_code, error_response = _build_error_response(e)
            yield _sse_data({"error": error_response.model_dump()})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/chat/agent", response_model=ChatResponse)
async def chat_agent(request: ChatRequest) -> ChatResponse:
    try:
        nl2sql = _get_nl2sql_pipeline()
        result = nl2sql.query_agent(
            question=request.question,
            conversation_id=request.conversation_id,
            datasource_id=request.datasource_id,
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
            "chart_data": result.get("chart_data"),
            "tool_calls": result.get("tool_calls") or [],
            "mode": result.get("mode", "agent"),
            "response_time_ms": result.get("response_time_ms"),
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
    """Agent 流式：落库 sql / sql_result / tool_calls / message_id"""
    import asyncio

    nl2sql = _get_nl2sql_pipeline()

    async def generate() -> AsyncGenerator[str, None]:
        try:
            full_answer: str = ""
            conv_id: str = request.conversation_id or str(uuid.uuid4())
            message_id: str = str(uuid.uuid4())
            last_sql: str = ""
            last_sql_result: dict | None = None
            last_tool_calls: list = []
            last_chart_data: dict | None = None
            last_response_time_ms: float = 0.0

            for event_str in nl2sql.query_agent_stream(
                request.question, conv_id, request.datasource_id,
            ):
                try:
                    event = json.loads(event_str)
                except json.JSONDecodeError:
                    yield f"data: {event_str}\n\n"
                    await asyncio.sleep(0)
                    continue

                if event.get("type") == "done":
                    full_answer = event.get("answer", "") or ""
                    last_sql = event.get("sql", "") or ""
                    last_sql_result = event.get("sql_result")
                    last_tool_calls = event.get("tool_calls") or []
                    last_chart_data = event.get("chart_data")
                    last_response_time_ms = float(event.get("response_time_ms") or 0)
                    event["message_id"] = message_id
                    event["conversation_id"] = event.get("conversation_id") or conv_id
                    event["has_numeric_data"] = last_chart_data is not None
                    yield _sse_data(event)
                else:
                    yield _sse_data(event)
                await asyncio.sleep(0)

            store = get_conversation_store()
            store.add_message(conv_id, {
                "id": message_id,
                "question": request.question,
                "answer": full_answer,
                "sql": last_sql,
                "sql_result": last_sql_result,
                "sources": [],
                "chart_data": last_chart_data,
                "tool_calls": last_tool_calls,
                "mode": "agent",
                "response_time_ms": last_response_time_ms,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            })
        except Exception as e:
            status_code, error_response = _build_error_response(e)
            yield _sse_data({"error": error_response.model_dump()})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
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
    """全量重建向量索引（清空后写入，避免重复累计）"""
    try:
        pipeline = get_pipeline()
        # 释放句柄 + 清空旧数据（create_from_documents 内也会再清一次）
        try:
            pipeline.vsm.reset_corrupt_index()
        except Exception as e:
            logger.warning(f"清理旧索引时警告: {e}")
        count: int = pipeline.build_index()
        stats = pipeline.get_stats()
        actual = stats.get("total_chunks", 0)
        return {
            "status": "ok",
            "chunks_written": count,
            "chunks_in_collection": actual,
            "vector_store_ready": stats.get("vector_store_ready", False),
            "total_chunks": actual,
            "note": (
                "若 chunks_in_collection 远大于预期，请停止后端后执行 "
                "python scripts/rebuild_index.py"
                if actual > count * 1.1
                else "全量重建完成"
            ),
        }
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
