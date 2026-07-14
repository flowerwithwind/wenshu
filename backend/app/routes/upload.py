"""文件上传路由"""
from __future__ import annotations

from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from app.services.file_upload import (
    validate_file, sanitize_table_name, save_uploaded_file, import_to_database
)
from app.logger import get_logger

logger = get_logger(__name__)

upload_router: APIRouter = APIRouter(prefix="/api", tags=["upload"])


@upload_router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    table_name: str | None = Form(None),
) -> dict:
    """上传并导入 CSV/Excel 文件"""
    # 1. 读取内容验证大小
    content: bytes = await file.read()
    error: str = validate_file(file.filename, len(content))
    if error:
        raise HTTPException(status_code=400, detail=error)

    # 2. 保存到 datasets/
    tname: str = table_name or sanitize_table_name(file.filename)
    file_path: str = save_uploaded_file(content, file.filename)

    # 3. 导入数据库
    try:
        result: dict = import_to_database(file_path, tname)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入数据库失败: {str(e)}")

    # 4. 重建向量索引
    chunks: int = 0
    try:
        from app.rag.pipeline import get_pipeline
        pipeline = get_pipeline()
        chunks = pipeline.build_index()
    except Exception as e:
        logger.warning(f"重建向量索引警告: {e}")

    return {
        "status": "ok",
        "table_name": tname,
        "row_count": result["row_count"],
        "columns": result["columns"],
        "chunks_added": chunks,
    }
