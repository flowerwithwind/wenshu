"""数据源管理 API：创建连接 / 导入数据 / 审计"""
from __future__ import annotations

import os
import tempfile
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.datasources.audit import list_audit
from app.datasources.manager import (
    create_record,
    delete_record,
    get_record,
    public_record,
    update_record,
)
from app.datasources.registry import (
    get_datasource,
    invalidate_datasource_cache,
    list_runtime_datasources,
)
from app.logger import get_logger
from app.services.ds_import import import_file_to_datasource, list_tables
from app.services.file_upload import validate_file
from app.services.knowledge_bootstrap import bootstrap_knowledge

logger = get_logger(__name__)

datasource_router: APIRouter = APIRouter(prefix="/api/datasources", tags=["datasources"])


class DataSourceCreate(BaseModel):
    name: str
    type: str = Field(..., description="sqlite | mysql | postgres")
    description: str = ""
    host: str = ""
    port: int | None = None
    database: str = ""
    username: str = ""
    password: str = ""
    is_default: bool = False


class DataSourceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    host: str | None = None
    port: int | None = None
    database: str | None = None
    username: str | None = None
    password: str | None = None
    is_default: bool | None = None


class DataSourceTestBody(BaseModel):
    id: str | None = None
    type: str | None = None
    host: str | None = None
    port: int | None = None
    database: str | None = None
    username: str | None = None
    password: str | None = None


@datasource_router.get("")
async def list_datasources() -> dict[str, Any]:
    return {"items": list_runtime_datasources()}


@datasource_router.get("/audit/logs")
async def audit_logs(limit: int = 100, datasource_id: str | None = None) -> dict[str, Any]:
    return {"items": list_audit(limit=limit, datasource_id=datasource_id)}


@datasource_router.post("/test")
async def test_datasource(body: DataSourceTestBody) -> dict[str, Any]:
    try:
        if body.id:
            ds = get_datasource(body.id)
            result = ds.test_connection()
            try:
                result["tables"] = list_tables(body.id)
                result["table_count"] = len(result["tables"])
            except Exception:
                pass
            return result

        from app.datasources.sqlalchemy_ds import SQLAlchemyDataSource
        from app.datasources.sqlite_ds import SqliteDataSource
        from app.config import BACKEND_ROOT
        import sqlite3
        from pathlib import Path

        t = (body.type or "mysql").lower()
        if t == "sqlite":
            # 草稿测试：使用临时空库或已有路径
            tmp = Path(BACKEND_ROOT) / "data" / "user_dbs" / "_tmp_test.db"
            tmp.parent.mkdir(parents=True, exist_ok=True)
            if not tmp.exists():
                sqlite3.connect(str(tmp)).close()
            ds = SqliteDataSource(
                ds_id="tmp-test",
                name="tmp",
                db_path=str(tmp),
                is_default=False,
                is_builtin=False,
            )
            return ds.test_connection()

        ds = SQLAlchemyDataSource(
            ds_id="tmp-test",
            name="tmp",
            db_type=t,
            host=body.host or "127.0.0.1",
            port=body.port,
            database=body.database or "",
            username=body.username or "",
            password=body.password or "",
        )
        result = ds.test_connection()
        ds.close()
        return result
    except Exception as e:
        return {"ok": False, "message": str(e), "latency_ms": 0}


@datasource_router.post("")
async def create_datasource(body: DataSourceCreate) -> dict[str, Any]:
    """仅创建连接/空库，不自动导入业务数据。"""
    try:
        rec = create_record(body.model_dump())
        # 创建后提示导入
        if rec.get("type") == "sqlite":
            rec["needs_import"] = True
            rec["next_step"] = "数据源已创建（空库）。请上传 CSV/Excel 导入表数据。"
        else:
            rec["next_step"] = (
                "连接已保存。若库中尚无业务表，请在此数据源上导入 CSV/Excel；"
                "若已有表可直接测试连接后用于智能问数。"
            )
        return rec
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@datasource_router.get("/{ds_id}")
async def get_datasource_api(ds_id: str) -> dict[str, Any]:
    rec = get_record(ds_id)
    if not rec:
        raise HTTPException(404, "数据源不存在")
    try:
        tables = list_tables(ds_id)
        tc = len(tables)
    except Exception:
        tables, tc = [], None
    out = public_record(rec, table_count=tc)
    out["tables"] = tables
    return out


@datasource_router.get("/{ds_id}/tables")
async def get_datasource_tables(ds_id: str) -> dict[str, Any]:
    if not get_record(ds_id):
        raise HTTPException(404, "数据源不存在")
    try:
        tables = list_tables(ds_id)
    except Exception as e:
        raise HTTPException(400, f"读取表列表失败: {e}") from e
    return {"datasource_id": ds_id, "tables": tables, "table_count": len(tables)}


@datasource_router.post("/{ds_id}/import")
async def import_to_datasource(
    ds_id: str,
    file: UploadFile = File(...),
    table_name: str | None = Form(None),
    use_llm: str | None = Form(None),
) -> dict[str, Any]:
    """向已创建的数据源导入一张 CSV/Excel 表，并自动 bootstrap 知识库。"""
    if not get_record(ds_id):
        raise HTTPException(404, "数据源不存在")
    content = await file.read()
    err = validate_file(file.filename or "upload.csv", len(content))
    if err:
        raise HTTPException(400, err)

    suffix = os.path.splitext(file.filename or ".csv")[1] or ".csv"
    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        result = import_file_to_datasource(ds_id, tmp_path, table_name)
        tables = list_tables(ds_id)
        use_llm_flag = str(use_llm or "").lower() in ("1", "true", "yes", "on")
        kb_info: dict[str, Any] = {}
        try:
            kb_info = bootstrap_knowledge(ds_id, use_llm=use_llm_flag, merge=True)
        except Exception as e:
            logger.warning(f"知识库 bootstrap 失败: {e}")
            kb_info = {"message": f"知识库自动生成失败: {e}", "examples_count": 0}
        return {
            "status": "ok",
            "message": (
                f"已导入表 {result['table_name']}（{result['row_count']} 行）。"
                f"{kb_info.get('message') or ''}"
            ).strip(),
            **result,
            "tables": tables,
            "table_count": len(tables),
            "needs_import": len(tables) == 0,
            "knowledge": kb_info,
        }
    except Exception as e:
        logger.exception("数据源导入失败")
        raise HTTPException(500, f"导入失败: {e}") from e
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


class BootstrapBody(BaseModel):
    use_llm: bool = False
    merge: bool = True


@datasource_router.post("/{ds_id}/bootstrap-knowledge")
async def bootstrap_knowledge_api(ds_id: str, body: BootstrapBody | None = None) -> dict[str, Any]:
    """手动（重新）扫描 Schema 生成知识库；可选 AI 增强。"""
    if not get_record(ds_id):
        raise HTTPException(404, "数据源不存在")
    body = body or BootstrapBody()
    try:
        return bootstrap_knowledge(ds_id, use_llm=body.use_llm, merge=body.merge)
    except Exception as e:
        logger.exception("bootstrap-knowledge failed")
        raise HTTPException(500, str(e)) from e


@datasource_router.put("/{ds_id}")
async def update_datasource(ds_id: str, body: DataSourceUpdate) -> dict[str, Any]:
    try:
        result = update_record(ds_id, body.model_dump(exclude_none=True))
        invalidate_datasource_cache(ds_id)
        return result
    except KeyError:
        raise HTTPException(404, "数据源不存在") from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@datasource_router.delete("/{ds_id}")
async def delete_datasource(ds_id: str) -> dict[str, str]:
    try:
        delete_record(ds_id)
        invalidate_datasource_cache(ds_id)
        # 删除对应知识库文件（非内置）
        try:
            from app.services.knowledge_manager import knowledge_path
            from app.datasources.sqlite_ds import BUILTIN_SQLITE_ID

            if ds_id != BUILTIN_SQLITE_ID:
                kp = knowledge_path(ds_id)
                if kp.exists() and "knowledge" in str(kp):
                    kp.unlink()
        except Exception as e:
            logger.warning(f"清理知识库文件失败: {e}")
        return {"status": "deleted"}
    except KeyError:
        raise HTTPException(404, "数据源不存在") from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
