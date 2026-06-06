"""
聊天 API 路由
"""
import uuid
import json
from typing import List
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    DatasetInfo,
    HistoryItem,
    HealthResponse,
)
from app.rag.pipeline import get_pipeline

router = APIRouter(prefix="/api", tags=["chat"])

# 内存中的对话历史存储（生产环境应使用数据库）
conversation_store: dict = {}


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """健康检查接口"""
    pipeline = get_pipeline()
    stats = pipeline.get_stats()
    return HealthResponse(
        status="ok",
        version="1.0.0",
        model="deepseek-chat" if stats["model_ready"] else "未配置",
        vector_store=f"就绪 ({stats['total_chunks']} 块)"
        if stats["vector_store_ready"]
        else "未初始化",
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """聊天接口 - 非流式"""
    try:
        pipeline = get_pipeline()
        result = pipeline.query(
            question=request.question,
            conversation_id=request.conversation_id,
        )

        # 保存对话历史
        conv_id = result["conversation_id"]
        if conv_id not in conversation_store:
            conversation_store[conv_id] = []
        conversation_store[conv_id].append({
            "id": result["id"],
            "question": request.question,
            "answer": result["answer"],
            "created_at": result["created_at"],
        })

        return ChatResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """聊天接口 - 流式输出"""
    pipeline = get_pipeline()

    async def generate():
        try:
            full_answer = ""
            for chunk in pipeline.query_stream(request.question):
                full_answer += chunk
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"

            conv_id = request.conversation_id or str(uuid.uuid4())
            if conv_id not in conversation_store:
                conversation_store[conv_id] = []
            conversation_store[conv_id].append({
                "id": str(uuid.uuid4()),
                "question": request.question,
                "answer": full_answer,
                "created_at": "",
            })

            yield f"data: {json.dumps({'done': True, 'conversation_id': conv_id})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.get("/history")
async def get_history():
    """获取所有对话历史"""
    history = []
    for conv_id, messages in conversation_store.items():
        history.append({
            "conversation_id": conv_id,
            "message_count": len(messages),
            "last_message": messages[-1]["question"][:50] if messages else "",
            "updated_at": messages[-1]["created_at"] if messages else "",
        })
    return {"conversations": sorted(
        history, key=lambda x: x["updated_at"], reverse=True
    )}


@router.get("/history/{conversation_id}")
async def get_conversation(conversation_id: str):
    """获取指定对话的详细内容"""
    messages = conversation_store.get(conversation_id, [])
    return {"conversation_id": conversation_id, "messages": messages}


@router.delete("/history/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """删除指定对话"""
    if conversation_id in conversation_store:
        del conversation_store[conversation_id]
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="对话不存在")


@router.post("/rebuild-index")
async def rebuild_index():
    """重建向量索引"""
    try:
        pipeline = get_pipeline()
        count = pipeline.build_index()
        return {"status": "ok", "chunks_created": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dataset-info", response_model=DatasetInfo)
async def get_dataset_info():
    """获取数据集信息"""
    pipeline = get_pipeline()
    stats = pipeline.get_stats()
    return DatasetInfo(
        name="知识库",
        file_count=0,
        total_chunks=stats["total_chunks"],
        last_updated=None,
    )