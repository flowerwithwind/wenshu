"""
SQLite 数据库模块 - 从 CSV 文件建表，提供 SQL 查询接口
支持5表星型模型: customers, products, orders, monthly_targets, refunds
"""
from __future__ import annotations

import os
import csv
import sqlite3
from typing import Any
from app.config import DATASET_DIR
from app.logger import get_logger

logger = get_logger(__name__)


DB_PATH: str = os.path.join(os.path.dirname(DATASET_DIR), "knowledge.db")

# CSV 文件到数据库表的映射 — 5表星型模型
CSV_TABLE_MAP: dict[str, dict[str, str]] = {
    "customers.csv": {
        "table": "customers",
        "description": "客户维度表(100人)，包含姓名、年龄、性别、注册日期、会员等级、所在省份"
    },
    "products.csv": {
        "table": "products",
        "description": "商品维度表(40款)，包含商品名称、品类、品牌、成本价、售价、上架日期"
    },
    "orders.csv": {
        "table": "orders",
        "description": "订单事实表(2023-2024,300笔)，包含日期、客户ID、商品ID、数量、售价、订单金额、折扣金额(NULL)、实付金额、支付方式、订单状态、收货省份。关联customers(客户ID)和products(商品ID)"
    },
    "monthly_targets.csv": {
        "table": "monthly_targets",
        "description": "月度销售目标表(2023-2024,8品类×24月)，包含年份、月份、品类、目标销售额"
    },
    "refunds.csv": {
        "table": "refunds",
        "description": "退款记录表(25笔,稀疏)，包含订单ID、退款金额、退款日期、退款原因(NULL)。关联orders(订单ID)"
    },
}


def normalize_column_name(name: str) -> str:
    """将中文列名规范化为 SQL 兼容的列名"""
    return name.strip()


def infer_sql_type(values: list[str]) -> str:
    """根据列值推断 SQL 类型"""
    # 先检查是否有空值（空字符串 = NULL），如果有空值则尝试从非空值推断
    non_empty: list[str] = [v for v in values if v and v.strip() != ""]
    if non_empty:
        for v in non_empty:
            try:
                int(v)
                return "INTEGER"
            except ValueError:
                pass
            try:
                float(v)
                return "REAL"
            except ValueError:
                pass
        return "TEXT"
    return "TEXT"


def init_database(db_path: str | None = None) -> sqlite3.Connection:
    """初始化数据库，从 CSV 文件创建表。

    db_path 默认取当前模块级 DB_PATH（运行时解析，便于测试/多数据源覆盖）。
    """
    if db_path is None:
        db_path = DB_PATH
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn: sqlite3.Connection = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    for csv_file, info in CSV_TABLE_MAP.items():
        csv_path: str = os.path.join(DATASET_DIR, csv_file)
        if not os.path.exists(csv_path):
            logger.warning(f"{csv_file} 不存在，跳过")
            continue

        table_name: str = info["table"]
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            headers: list[str] = next(reader)
            headers = [normalize_column_name(h) for h in headers]
            all_rows: list[list[str]] = list(reader)

        # 推断列类型
        col_types: dict[str, str] = {}
        for i, header in enumerate(headers):
            col_values: list[str] = [row[i] for row in all_rows if i < len(row)]
            col_types[header] = infer_sql_type(col_values)

        # 先删除旧表再创建
        conn.execute(f"DROP TABLE IF EXISTS [{table_name}]")
        col_defs: str = ", ".join(f"[{h}] {col_types[h]}" for h in headers)
        create_sql: str = f"CREATE TABLE [{table_name}] ({col_defs})"
        conn.execute(create_sql)

        # 插入数据
        placeholders: str = ", ".join("?" for _ in headers)
        insert_sql: str = f"INSERT INTO [{table_name}] VALUES ({placeholders})"
        for row in all_rows:
            values: list[Any] = []
            for i, v in enumerate(row):
                h: str = headers[i]
                ct: str = col_types[h]
                if not v or v.strip() == "":
                    values.append(None)
                elif ct == "INTEGER":
                    try:
                        values.append(int(v))
                    except ValueError:
                        values.append(v)
                elif ct == "REAL":
                    try:
                        values.append(float(v))
                    except ValueError:
                        values.append(v)
                else:
                    values.append(v)
            conn.execute(insert_sql, values)

        conn.commit()
        col_info: str = ", ".join(f"{h}({col_types[h]})" for h in headers)
        logger.info(f"表 [{table_name}]: {len(all_rows)} 行 ({col_info})")

    # 创建索引加速 JOIN 查询
    _create_indexes(conn)
    return conn


def _create_indexes(conn: sqlite3.Connection) -> None:
    """创建常用 JOIN 列索引"""
    indexes: list[tuple[str, str, str]] = [
        ("idx_orders_customer", "orders", "客户ID"),
        ("idx_orders_product", "orders", "商品ID"),
        ("idx_orders_date", "orders", "日期"),
        ("idx_orders_status", "orders", "订单状态"),
        ("idx_refunds_order", "refunds", "订单ID"),
        ("idx_targets_composite", "monthly_targets", "年份, 月份, 品类"),
    ]
    for idx_name, table, cols in indexes:
        try:
            conn.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON [{table}] ({cols})")
        except sqlite3.OperationalError:
            pass
    conn.commit()


def _validate_sql_safety(sql: str) -> None:
    """校验 SQL 安全性（委托统一 safety 模块，保持旧 import 兼容）"""
    from app.datasources.safety import validate_sql_safety

    validate_sql_safety(sql)


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """获取数据库连接（db_path 默认取当前模块级 DB_PATH）"""
    if db_path is None:
        db_path = DB_PATH
    conn: sqlite3.Connection = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def get_schema_info(db_path: str | None = None) -> str:
    """获取所有表的 Schema 信息（供 NL2SQL 提示词使用）。

    - 内置电商库：带中文业务说明与 JOIN 关系
    - 其它 SQLite 文件：自动 introspect 全部用户表
    """
    if db_path is None:
        db_path = DB_PATH
    conn: sqlite3.Connection = get_connection(db_path)
    cursor: sqlite3.Cursor = conn.cursor()

    schema_parts: list[str] = []
    # 比较“内置电商库”路径：用模块导入时的默认路径常量判断会失效，
    # 这里把带完整 5 表业务说明的条件限定为“路径指向 knowledge.db 且表齐全”。
    default_builtin = os.path.join(os.path.dirname(DATASET_DIR), "knowledge.db")
    is_builtin_ecommerce = os.path.normpath(db_path) == os.path.normpath(default_builtin)

    if is_builtin_ecommerce:
        for _csv_file, info in CSV_TABLE_MAP.items():
            table_name: str = info["table"]
            try:
                cursor.execute(f"SELECT * FROM [{table_name}] LIMIT 0")
                columns: list[str] = [desc[0] for desc in cursor.description]
                cursor.execute(f"SELECT * FROM [{table_name}] LIMIT 1")
                sample_row: sqlite3.Row | None = cursor.fetchone()

                schema_parts.append(f"表 [{table_name}]: {info['description']}")
                schema_parts.append(f"  列: {', '.join(columns)}")
                if sample_row:
                    schema_parts.append(f"  示例: {dict(sample_row)}")
            except sqlite3.OperationalError:
                pass

        schema_parts.append("\n--- 表关联关系 ---")
        schema_parts.append("[orders].[客户ID] -> [customers].[客户ID] (INNER JOIN)")
        schema_parts.append("[orders].[商品ID] -> [products].[商品ID] (INNER JOIN)")
        schema_parts.append("[refunds].[订单ID] -> [orders].[订单ID] (LEFT JOIN, 退款分析)")
        schema_parts.append(
            "[orders] vs [monthly_targets]: 通过 年份+月份+品类 关联(达成率分析)"
        )
    else:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
        tables = [r[0] for r in cursor.fetchall()]
        schema_parts.append(f"方言: sqlite；数据库文件: {os.path.basename(db_path)}")
        schema_parts.append("标识符请用方括号 [table]/[column]")
        for table_name in tables:
            try:
                cursor.execute(f"PRAGMA table_info([{table_name}])")
                cols_info = cursor.fetchall()
                columns = [c[1] for c in cols_info]
                cursor.execute(f"SELECT * FROM [{table_name}] LIMIT 1")
                sample_row = cursor.fetchone()
                schema_parts.append(f"表 [{table_name}]: 列: {', '.join(columns)}")
                if sample_row:
                    schema_parts.append(f"  示例: {dict(sample_row)}")
            except sqlite3.OperationalError as e:
                schema_parts.append(f"表 [{table_name}]: 读取失败 ({e})")
        if not tables:
            schema_parts.append("（当前库尚无任何表，请先在数据源管理中导入 CSV/Excel）")

    conn.close()
    return "\n".join(schema_parts)


def execute_sql(sql: str, db_path: str | None = None) -> tuple[list[dict[str, Any]], list[str]]:
    """执行 SQL 查询，返回结果行和列名（db_path 默认取当前模块级 DB_PATH）"""
    if db_path is None:
        db_path = DB_PATH
    _validate_sql_safety(sql)

    # SQL 级别缓存（按库路径隔离，避免多数据源串缓存）
    from app.services.cache import get_cache as get_sql_cache

    cache_key = f"sql::{os.path.normpath(db_path)}::{sql}"
    cached: dict | None = get_sql_cache(cache_key)
    if cached:
        logger.debug("SQL 命中缓存")
        return cached["rows"], cached["columns"]

    conn: sqlite3.Connection = get_connection(db_path)
    cursor: sqlite3.Cursor = conn.cursor()
    cursor.execute(sql)
    columns: list[str] = [desc[0] for desc in cursor.description] if cursor.description else []
    rows: list[dict[str, Any]] = [dict(row) for row in cursor.fetchall()]

    # 限制返回行数：超过 1000 行时只返回前 1000 行
    original_count: int = len(rows)
    if original_count > 1000:
        rows = rows[:1000]
        logger.info(f"结果已截断: {original_count} → 1000 行")

    conn.close()

    from app.services.cache import set_cache as set_sql_cache

    set_sql_cache(cache_key, {"rows": rows, "columns": columns})

    return rows, columns


def is_database_ready(db_path: str | None = None) -> bool:
    """检查数据库是否就绪（db_path 默认取当前模块级 DB_PATH）"""
    if db_path is None:
        db_path = DB_PATH
    if not os.path.exists(db_path):
        return False
    conn: sqlite3.Connection = get_connection(db_path)
    cursor: sqlite3.Cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables: list[str] = [row[0] for row in cursor.fetchall()]
    conn.close()
    return len(tables) > 0
