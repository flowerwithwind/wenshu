"""向指定数据源导入 CSV/Excel 表"""
from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd

from app.datasources.registry import get_datasource, invalidate_datasource_cache
from app.logger import get_logger
from app.nl2sql.database import infer_sql_type, normalize_column_name

logger = get_logger(__name__)


def sanitize_table_name(name: str) -> str:
    base = os.path.splitext(os.path.basename(name))[0]
    base = re.sub(r"[^a-zA-Z0-9_一-鿿]", "_", base)
    return (base or "imported_table")[:50]


def _read_dataframe(file_path: str) -> pd.DataFrame:
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".csv":
        return pd.read_csv(file_path, encoding="utf-8-sig", low_memory=False)
    if ext in (".xlsx", ".xls"):
        return pd.read_excel(file_path, engine="openpyxl")
    raise ValueError(f"不支持的文件类型: {ext}")


def import_file_to_datasource(
    ds_id: str,
    file_path: str,
    table_name: str | None = None,
) -> dict[str, Any]:
    """将本地文件导入指定数据源，返回表名/行数/列。"""
    ds = get_datasource(ds_id)
    tname = sanitize_table_name(table_name or Path(file_path).name)
    df = _read_dataframe(file_path)
    if df.empty:
        raise ValueError("文件内容为空")

    # 规范化列名
    df.columns = [normalize_column_name(str(c)) for c in df.columns]

    dialect = (ds.dialect or "sqlite").lower()
    if dialect == "sqlite" or ds.meta.type == "sqlite":
        db_path = ds.meta.extra.get("path") or ""
        if not db_path:
            raise ValueError("SQLite 数据源缺少文件路径")
        _import_sqlite(db_path, tname, df)
    else:
        _import_sqlalchemy(ds, tname, df)

    invalidate_datasource_cache(ds_id)
    logger.info(f"导入表 {tname} → 数据源 {ds_id} rows={len(df)}")
    return {
        "table_name": tname,
        "row_count": int(len(df)),
        "columns": list(df.columns),
        "datasource_id": ds_id,
    }


def _import_sqlite(db_path: str, table_name: str, df: pd.DataFrame) -> None:
    headers = list(df.columns)
    rows = df.values.tolist()
    col_types: dict[str, str] = {}
    for i, h in enumerate(headers):
        vals = [
            "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v)
            for v in (row[i] for row in rows if i < len(row))
        ]
        col_types[h] = infer_sql_type(vals)

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(f"DROP TABLE IF EXISTS [{table_name}]")
        col_defs = ", ".join(f"[{h}] {col_types[h]}" for h in headers)
        conn.execute(f"CREATE TABLE [{table_name}] ({col_defs})")
        placeholders = ", ".join("?" for _ in headers)
        insert_sql = f"INSERT INTO [{table_name}] VALUES ({placeholders})"
        for row in rows:
            values: list[Any] = []
            for i, v in enumerate(row):
                h = headers[i]
                ct = col_types[h]
                if v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() == "":
                    values.append(None)
                elif ct == "INTEGER":
                    try:
                        values.append(int(float(v)))
                    except (TypeError, ValueError):
                        values.append(None)
                elif ct == "REAL":
                    try:
                        values.append(float(v))
                    except (TypeError, ValueError):
                        values.append(None)
                else:
                    values.append(str(v))
            conn.execute(insert_sql, values)
        conn.commit()
    finally:
        conn.close()


def _import_sqlalchemy(ds: Any, table_name: str, df: pd.DataFrame) -> None:
    from sqlalchemy import text

    # SQLAlchemyDataSource 内部引擎
    eng = ds._engine()  # noqa: SLF001 — 导入场景需要
    # 分块写入
    first = True
    for start in range(0, len(df), 5000):
        chunk = df.iloc[start : start + 5000]
        chunk.to_sql(
            table_name,
            eng,
            if_exists="replace" if first else "append",
            index=False,
            method="multi",
            chunksize=500,
        )
        first = False
    # 简单索引：对 *_id 列
    with eng.begin() as conn:
        for col in df.columns:
            cl = str(col).lower()
            if cl == "id" or cl.endswith("_id"):
                idx = f"idx_{table_name}_{col}"[:60]
                try:
                    qcol = ds._quote_ident(col)  # noqa: SLF001
                    qtable = ds._quote_ident(table_name)  # noqa: SLF001
                    conn.execute(text(f"CREATE INDEX {idx} ON {qtable} ({qcol})"))
                except Exception:
                    pass


def list_tables(ds_id: str) -> list[str]:
    ds = get_datasource(ds_id)
    if ds.meta.type == "sqlite":
        path = ds.meta.extra.get("path") or ""
        if not path or not os.path.exists(path):
            return []
        conn = sqlite3.connect(path)
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
            return [r[0] for r in cur.fetchall()]
        finally:
            conn.close()
    # MySQL/PG
    from sqlalchemy import inspect

    eng = ds._engine()  # noqa: SLF001
    return list(inspect(eng).get_table_names())
