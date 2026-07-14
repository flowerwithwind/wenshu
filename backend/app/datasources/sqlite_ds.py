"""内置 SQLite 数据源（电商 knowledge.db）"""
from __future__ import annotations

import os
import time
from typing import Any

from app.config import DATASET_DIR
from app.datasources.base import DataSource, DataSourceMeta
from app.datasources.safety import validate_sql_safety
from app.logger import get_logger
from app.nl2sql import database as db_module

logger = get_logger(__name__)

BUILTIN_SQLITE_ID: str = "builtin-sqlite"


class SqliteDataSource(DataSource):
    """封装现有 knowledge.db 逻辑"""

    def __init__(
        self,
        ds_id: str = BUILTIN_SQLITE_ID,
        name: str = "电商演示库 (SQLite)",
        db_path: str | None = None,
        is_default: bool = True,
        is_builtin: bool = True,
        description: str = "内置电商星型模型：customers/products/orders/monthly_targets/refunds",
    ) -> None:
        self._db_path: str = db_path or db_module.DB_PATH
        self._meta = DataSourceMeta(
            id=ds_id,
            name=name,
            type="sqlite",
            dialect="sqlite",
            description=description,
            is_default=is_default,
            is_builtin=is_builtin,
            database=os.path.basename(self._db_path),
            extra={"path": self._db_path, "dataset_dir": DATASET_DIR},
        )

    @property
    def meta(self) -> DataSourceMeta:
        return self._meta

    def is_ready(self) -> bool:
        return db_module.is_database_ready(self._db_path)

    def test_connection(self) -> dict[str, Any]:
        start = time.time()
        try:
            if not os.path.exists(self._db_path):
                return {
                    "ok": False,
                    "message": f"数据库文件不存在: {self._db_path}",
                    "latency_ms": 0,
                }
            ready = self.is_ready()
            latency = round((time.time() - start) * 1000, 2)
            if not ready:
                return {"ok": False, "message": "数据库无表，请先初始化", "latency_ms": latency}
            conn = db_module.get_connection(self._db_path)
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in cur.fetchall()]
            conn.close()
            return {
                "ok": True,
                "message": f"连接成功，共 {len(tables)} 张表",
                "latency_ms": latency,
                "tables": tables,
            }
        except Exception as e:
            return {
                "ok": False,
                "message": str(e),
                "latency_ms": round((time.time() - start) * 1000, 2),
            }

    def get_schema_info(self) -> str:
        return db_module.get_schema_info(self._db_path)

    def execute_sql(self, sql: str) -> tuple[list[dict[str, Any]], list[str]]:
        validate_sql_safety(sql)
        # 复用现有实现（含缓存与限行）
        return db_module.execute_sql(sql, self._db_path)
