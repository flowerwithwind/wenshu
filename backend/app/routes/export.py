"""数据导出路由"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from app.services.conversation_store import get_conversation_store
from app.services.export_service import export_to_csv, export_to_excel

export_router: APIRouter = APIRouter(prefix="/api", tags=["export"])


@export_router.get("/export")
async def export_result(
    conversation_id: str = Query(..., description="对话ID"),
    message_id: str = Query(..., description="消息ID"),
    format: str = Query("csv", description="导出格式: csv 或 xlsx"),
) -> Response:
    """导出指定对话中某条消息的查询结果"""
    store = get_conversation_store()
    conv = store.get(conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="对话不存在")

    # 找到对应消息
    target_msg: dict | None = None
    for msg in conv.get("messages", []):
        if msg.get("id") == message_id:
            target_msg = msg
            break

    if target_msg is None:
        raise HTTPException(status_code=404, detail="消息不存在")

    sql_result: dict | None = target_msg.get("sql_result")
    if not sql_result:
        raise HTTPException(status_code=400, detail="该消息无查询结果")

    columns: list[str] = sql_result.get("columns", [])
    rows: list[dict] = sql_result.get("rows", [])

    if not columns or not rows:
        raise HTTPException(status_code=400, detail="无数据可导出")

    if format == "xlsx":
        data: bytes = export_to_excel(columns, rows)
        return Response(
            content=data,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=query_result.xlsx"},
        )
    else:
        data = export_to_csv(columns, rows)
        return Response(
            content=data,
            media_type="text/csv; charset=utf-8-sig",
            headers={"Content-Disposition": f"attachment; filename=query_result.csv"},
        )
