"""数据源运行时注册表：按 id 构建 DataSource 实例"""
from __future__ import annotations

import time
from typing import Any

from app.datasources.audit import write_audit
from app.datasources.base import DataSource
from app.datasources.manager import get_password, get_record, list_datasource_records
from app.datasources.sqlite_ds import BUILTIN_SQLITE_ID, SqliteDataSource
from app.datasources.sqlalchemy_ds import SQLAlchemyDataSource
from app.logger import get_logger

logger = get_logger(__name__)

_cache: dict[str, DataSource] = {}


def _build_from_record(rec: dict[str, Any]) -> DataSource:
    ds_type = (rec.get("type") or "sqlite").lower()
    ds_id = rec["id"]
    if ds_type == "sqlite" or ds_id == BUILTIN_SQLITE_ID:
        return SqliteDataSource(
            ds_id=ds_id,
            name=rec.get("name") or "SQLite",
            is_default=bool(rec.get("is_default")),
            is_builtin=bool(rec.get("is_builtin")),
            description=rec.get("description") or "",
        )

    password = get_password(rec)
    return SQLAlchemyDataSource(
        ds_id=ds_id,
        name=rec.get("name") or ds_type,
        db_type=ds_type,
        host=rec.get("host") or "127.0.0.1",
        port=rec.get("port"),
        database=rec.get("database") or "",
        username=rec.get("username") or "",
        password=password,
        description=rec.get("description") or "",
        is_default=bool(rec.get("is_default")),
        is_builtin=False,
    )


def invalidate_datasource_cache(ds_id: str | None = None) -> None:
    global _cache
    if ds_id is None:
        for ds in list(_cache.values()):
            try:
                ds.close()
            except Exception:
                pass
        _cache = {}
        return
    ds = _cache.pop(ds_id, None)
    if ds is not None:
        try:
            ds.close()
        except Exception:
            pass


def get_datasource(ds_id: str | None = None) -> DataSource:
    """获取数据源；None / 空 → 默认源。"""
    if not ds_id:
        return get_default_datasource()

    if ds_id in _cache:
        return _cache[ds_id]

    rec = get_record(ds_id)
    if not rec:
        logger.warning(f"数据源 {ds_id} 不存在，回退默认")
        return get_default_datasource()

    ds = _build_from_record(rec)
    _cache[ds_id] = ds
    return ds


def get_default_datasource() -> DataSource:
    records = list_datasource_records()
    default_id = BUILTIN_SQLITE_ID
    for r in records:
        if r.get("is_default"):
            default_id = r["id"]
            break
    if default_id in _cache:
        return _cache[default_id]
    rec = get_record(default_id) or {
        "id": BUILTIN_SQLITE_ID,
        "name": "电商演示库 (SQLite)",
        "type": "sqlite",
        "is_default": True,
        "is_builtin": True,
    }
    ds = _build_from_record(rec)
    _cache[default_id] = ds
    return ds


def list_runtime_datasources() -> list[dict[str, Any]]:
    from app.datasources.manager import public_record

    return [public_record(r) for r in list_datasource_records()]


def execute_with_audit(
    ds: DataSource,
    sql: str,
    *,
    source: str = "pipeline",
    request_id: str = "",
) -> tuple[list[dict[str, Any]], list[str]]:
    """执行 SQL 并写审计。"""
    start = time.time()
    try:
        rows, cols = ds.execute_sql(sql)
        write_audit(
            datasource_id=ds.meta.id,
            datasource_name=ds.meta.name,
            sql=sql,
            ok=True,
            row_count=len(rows),
            duration_ms=round((time.time() - start) * 1000, 2),
            source=source,
            request_id=request_id,
        )
        return rows, cols
    except Exception as e:
        write_audit(
            datasource_id=ds.meta.id,
            datasource_name=ds.meta.name,
            sql=sql,
            ok=False,
            error=str(e),
            duration_ms=round((time.time() - start) * 1000, 2),
            source=source,
            request_id=request_id,
        )
        raise
