"""数据源管理 API"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.datasources.audit import list_audit
from app.datasources.manager import (
    create_record,
    delete_record,
    get_record,
    public_record,
    update_record,
)
from app.datasources.registry import get_datasource, invalidate_datasource_cache, list_runtime_datasources
from app.datasources.sqlite_ds import BUILTIN_SQLITE_ID
from app.logger import get_logger

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
            return ds.test_connection()

        from app.datasources.sqlalchemy_ds import SQLAlchemyDataSource
        from app.datasources.sqlite_ds import SqliteDataSource

        t = (body.type or "mysql").lower()
        if t == "sqlite":
            ds = SqliteDataSource(ds_id="tmp-test", name="tmp", is_default=False, is_builtin=False)
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
    try:
        return create_record(body.model_dump())
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@datasource_router.get("/{ds_id}")
async def get_datasource_api(ds_id: str) -> dict[str, Any]:
    rec = get_record(ds_id)
    if not rec:
        raise HTTPException(404, "数据源不存在")
    return public_record(rec)


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
        return {"status": "deleted"}
    except KeyError:
        raise HTTPException(404, "数据源不存在") from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
