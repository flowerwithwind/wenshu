"""文件上传服务：解析 CSV/Excel → 写入 SQLite → 更新 CSV_TABLE_MAP"""
from __future__ import annotations

import os
import re
import sqlite3
from typing import Any

import pandas as pd

from app.config import DATASET_DIR, MAX_UPLOAD_SIZE_MB
import app.nl2sql.database as db_module
from app.nl2sql.database import CSV_TABLE_MAP, infer_sql_type, normalize_column_name
from app.logger import get_logger

logger = get_logger(__name__)

ALLOWED_EXTENSIONS: set[str] = {'.csv', '.xlsx', '.xls'}
MAX_SIZE_BYTES: int = MAX_UPLOAD_SIZE_MB * 1024 * 1024


def validate_file(filename: str, size: int) -> str:
    """验证文件：检查扩展名、大小。返回错误信息或空字符串"""
    ext: str = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return f"不支持的文件类型 {ext}，仅支持 {', '.join(ALLOWED_EXTENSIONS)}"
    if size > MAX_SIZE_BYTES:
        return f"文件大小超过限制（最大 {MAX_UPLOAD_SIZE_MB}MB）"
    if size == 0:
        return "文件为空"
    return ""


def sanitize_table_name(filename: str) -> str:
    """从文件名生成安全的表名：去扩展名、替换特殊字符为_、限制长度"""
    name: str = os.path.splitext(filename)[0]
    name = re.sub(r'[^a-zA-Z0-9一-鿿_]', '_', name)
    return name[:50]


def save_uploaded_file(content: bytes, filename: str, target_dir: str | None = None) -> str:
    """保存上传文件到 datasets/ 目录，返回保存的完整路径"""
    if target_dir is None:
        target_dir = DATASET_DIR
    os.makedirs(target_dir, exist_ok=True)
    file_path: str = os.path.join(target_dir, filename)
    with open(file_path, 'wb') as f:
        f.write(content)
    return file_path


def import_to_database(file_path: str, table_name: str) -> dict[str, Any]:
    """
    将 CSV/Excel 导入 SQLite：
    1. pandas 读取文件
    2. 推断列类型（复用 database.infer_sql_type 逻辑）
    3. DROP TABLE IF EXISTS → CREATE TABLE → 批量 INSERT
    4. 更新 CSV_TABLE_MAP
    5. 返回: {"table_name": str, "row_count": int, "columns": [str]}
    """
    ext: str = os.path.splitext(file_path)[1].lower()

    # 读取文件
    if ext == '.csv':
        df: pd.DataFrame = pd.read_csv(file_path, encoding='utf-8-sig')
    else:
        df = pd.read_excel(file_path, engine='openpyxl')

    if df.empty:
        raise ValueError("文件内容为空")

    headers: list[str] = [normalize_column_name(h) for h in df.columns.tolist()]
    all_rows: list[list[Any]] = df.values.tolist()

    # 推断列类型
    col_types: dict[str, str] = {}
    for i, header in enumerate(headers):
        col_values: list[str] = [str(row[i]) if row[i] is not None and str(row[i]) != 'nan' else ''
                                  for row in all_rows if i < len(row)]
        col_types[header] = infer_sql_type(col_values)

    # 写入数据库（运行时读取 DB_PATH，避免 import 时绑定导致测试/多库失效）
    conn: sqlite3.Connection = sqlite3.connect(db_module.DB_PATH)
    conn.row_factory = sqlite3.Row

    conn.execute(f"DROP TABLE IF EXISTS [{table_name}]")
    col_defs: str = ", ".join(f"[{h}] {col_types[h]}" for h in headers)
    create_sql: str = f"CREATE TABLE [{table_name}] ({col_defs})"
    conn.execute(create_sql)

    placeholders: str = ", ".join("?" for _ in headers)
    insert_sql: str = f"INSERT INTO [{table_name}] VALUES ({placeholders})"
    for row in all_rows:
        values: list[Any] = []
        for i, v in enumerate(row):
            h: str = headers[i]
            ct: str = col_types[h]
            if v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() == '':
                values.append(None)
            elif ct == "INTEGER":
                try:
                    values.append(int(float(v)))
                except (ValueError, TypeError):
                    values.append(str(v))
            elif ct == "REAL":
                try:
                    values.append(float(v))
                except (ValueError, TypeError):
                    values.append(str(v))
            else:
                values.append(str(v))
        conn.execute(insert_sql, values)

    conn.commit()
    conn.close()

    # 更新 CSV_TABLE_MAP
    filename: str = os.path.basename(file_path)
    CSV_TABLE_MAP[filename] = {
        "table": table_name,
        "description": f"用户上传: {table_name} ({len(all_rows)} 行)"
    }

    col_info: str = ", ".join(f"{h}({col_types[h]})" for h in headers)
    logger.info(f"表 [{table_name}]: {len(all_rows)} 行 ({col_info})")

    return {
        "table_name": table_name,
        "row_count": len(all_rows),
        "columns": headers,
    }
