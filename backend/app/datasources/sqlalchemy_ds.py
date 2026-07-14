"""MySQL / PostgreSQL 数据源（SQLAlchemy 连接池）"""
from __future__ import annotations

import time
from typing import Any

from app.datasources.base import DataSource, DataSourceMeta
from app.datasources.pool import dispose_engine, get_engine
from app.datasources.safety import validate_sql_safety
from app.logger import get_logger

logger = get_logger(__name__)

MAX_ROWS: int = 1000


class SQLAlchemyDataSource(DataSource):
    def __init__(
        self,
        ds_id: str,
        name: str,
        db_type: str,
        host: str,
        port: int | None,
        database: str,
        username: str,
        password: str,
        description: str = "",
        is_default: bool = False,
        is_builtin: bool = False,
    ) -> None:
        dialect = "mysql" if db_type.lower() == "mysql" else "postgres"
        self._db_type = db_type.lower()
        self._host = host
        self._port = port
        self._database = database
        self._username = username
        self._password = password
        self._meta = DataSourceMeta(
            id=ds_id,
            name=name,
            type=self._db_type if self._db_type != "postgresql" else "postgres",
            dialect=dialect,
            description=description,
            is_default=is_default,
            is_builtin=is_builtin,
            host=host,
            port=port,
            database=database,
            username=username,
        )

    @property
    def meta(self) -> DataSourceMeta:
        return self._meta

    def _engine(self):
        return get_engine(
            self._meta.id,
            self._db_type,
            self._host,
            self._port,
            self._database,
            self._username,
            self._password,
        )

    def is_ready(self) -> bool:
        try:
            r = self.test_connection()
            return bool(r.get("ok"))
        except Exception:
            return False

    def test_connection(self) -> dict[str, Any]:
        start = time.time()
        try:
            from sqlalchemy import text

            eng = self._engine()
            with eng.connect() as conn:
                conn.execute(text("SELECT 1"))
            return {
                "ok": True,
                "message": "连接成功",
                "latency_ms": round((time.time() - start) * 1000, 2),
            }
        except Exception as e:
            return {
                "ok": False,
                "message": str(e),
                "latency_ms": round((time.time() - start) * 1000, 2),
            }

    def get_schema_info(self) -> str:
        from sqlalchemy import inspect, text

        eng = self._engine()
        insp = inspect(eng)
        parts: list[str] = []
        dialect = self.dialect
        try:
            tables = insp.get_table_names()
        except Exception as e:
            return f"获取表列表失败: {e}"

        for table in tables[:80]:
            try:
                cols = insp.get_columns(table)
                col_desc = ", ".join(
                    f"{c['name']}({getattr(c.get('type'), '__class__', type(c.get('type'))).__name__})"
                    for c in cols
                )
                parts.append(f"表 {table}: 列: {col_desc}")
                # 样例行
                q = self._quote_ident(table)
                with eng.connect() as conn:
                    rows = conn.execute(text(f"SELECT * FROM {q} LIMIT 1")).mappings().all()
                    if rows:
                        parts.append(f"  示例: {dict(rows[0])}")
            except Exception as e:
                parts.append(f"表 {table}: 读取失败 ({e})")

        parts.append(f"\n--- 方言: {dialect} ---")
        if dialect == "mysql":
            parts.append("标识符用反引号 `table`；字符串单引号；日期 DATE_FORMAT / YEAR()")
        else:
            parts.append('标识符用双引号 "table"；字符串单引号；日期 to_char / date_trunc')
        return "\n".join(parts)

    def execute_sql(self, sql: str) -> tuple[list[dict[str, Any]], list[str]]:
        from sqlalchemy import text

        validate_sql_safety(sql)
        eng = self._engine()
        with eng.connect() as conn:
            result = conn.execute(text(sql))
            if result.returns_rows:
                columns = list(result.keys())
                rows = [dict(r) for r in result.mappings().fetchmany(MAX_ROWS + 1)]
                if len(rows) > MAX_ROWS:
                    rows = rows[:MAX_ROWS]
                    logger.info(f"结果已截断 → {MAX_ROWS} 行")
                # 序列化不可 JSON 类型
                clean_rows: list[dict[str, Any]] = []
                for row in rows:
                    clean_rows.append({k: _jsonable(v) for k, v in row.items()})
                return clean_rows, columns
            return [], []

    def close(self) -> None:
        dispose_engine(self._meta.id)


def _jsonable(v: Any) -> Any:
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    if hasattr(v, "isoformat"):
        try:
            return v.isoformat()
        except Exception:
            return str(v)
    return str(v)
