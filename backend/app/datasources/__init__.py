"""多数据源抽象层"""
from __future__ import annotations

from app.datasources.base import DataSource, DataSourceMeta
from app.datasources.registry import get_datasource, get_default_datasource, list_runtime_datasources

__all__ = [
    "DataSource",
    "DataSourceMeta",
    "get_datasource",
    "get_default_datasource",
    "list_runtime_datasources",
]
