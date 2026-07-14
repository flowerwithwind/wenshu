"""请求级当前数据源上下文（供 Agent tools 使用）"""
from __future__ import annotations

from contextvars import ContextVar

from app.datasources.base import DataSource
from app.datasources.registry import get_default_datasource

_current_ds: ContextVar[DataSource | None] = ContextVar("current_datasource", default=None)
_current_ds_id: ContextVar[str | None] = ContextVar("current_datasource_id", default=None)


def set_current_datasource(ds: DataSource | None, ds_id: str | None = None) -> None:
    _current_ds.set(ds)
    _current_ds_id.set(ds_id or (ds.meta.id if ds else None))


def get_current_datasource() -> DataSource:
    ds = _current_ds.get()
    if ds is not None:
        return ds
    return get_default_datasource()


def get_current_datasource_id() -> str | None:
    return _current_ds_id.get()
