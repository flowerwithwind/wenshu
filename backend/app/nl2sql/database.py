"""
SQLite 数据库模块 - 从 CSV 文件建表，提供 SQL 查询接口
支持5表星型模型: customers, products, orders, monthly_targets, refunds
"""
import os
import csv
import sqlite3
from typing import List, Dict, Any, Tuple, Optional
from app.config import DATASET_DIR


DB_PATH = os.path.join(os.path.dirname(DATASET_DIR), "knowledge.db")

# CSV 文件到数据库表的映射 — 5表星型模型
CSV_TABLE_MAP = {
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


def infer_sql_type(values: List[str]) -> str:
    """根据列值推断 SQL 类型"""
    # 先检查是否有空值（空字符串 = NULL），如果有空值则尝试从非空值推断
    non_empty = [v for v in values if v and v.strip() != ""]
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


def init_database(db_path: str = DB_PATH) -> sqlite3.Connection:
    """初始化数据库，从 CSV 文件创建表"""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    for csv_file, info in CSV_TABLE_MAP.items():
        csv_path = os.path.join(DATASET_DIR, csv_file)
        if not os.path.exists(csv_path):
            print(f"  [SKIP] {csv_file} 不存在，跳过")
            continue

        table_name = info["table"]
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            headers = next(reader)
            headers = [normalize_column_name(h) for h in headers]
            all_rows = list(reader)

        # 推断列类型
        col_types = {}
        for i, header in enumerate(headers):
            col_values = [row[i] for row in all_rows if i < len(row)]
            col_types[header] = infer_sql_type(col_values)

        # 先删除旧表再创建
        conn.execute(f"DROP TABLE IF EXISTS [{table_name}]")
        col_defs = ", ".join(f"[{h}] {col_types[h]}" for h in headers)
        create_sql = f"CREATE TABLE [{table_name}] ({col_defs})"
        conn.execute(create_sql)

        # 插入数据
        placeholders = ", ".join("?" for _ in headers)
        insert_sql = f"INSERT INTO [{table_name}] VALUES ({placeholders})"
        for row in all_rows:
            values = []
            for i, v in enumerate(row):
                h = headers[i]
                ct = col_types[h]
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
        col_info = ", ".join(f"{h}({col_types[h]})" for h in headers)
        print(f"  [OK] 表 [{table_name}]: {len(all_rows)} 行 ({col_info})")

    # 创建索引加速 JOIN 查询
    _create_indexes(conn)
    return conn


def _create_indexes(conn: sqlite3.Connection):
    """创建常用 JOIN 列索引"""
    indexes = [
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


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """获取数据库连接"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def get_schema_info(db_path: str = DB_PATH) -> str:
    """获取所有表的 Schema 信息（供 NL2SQL 提示词使用）"""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    schema_parts = []
    for csv_file, info in CSV_TABLE_MAP.items():
        table_name = info["table"]
        try:
            cursor.execute(f"SELECT * FROM [{table_name}] LIMIT 0")
            columns = [desc[0] for desc in cursor.description]
            cursor.execute(f"SELECT * FROM [{table_name}] LIMIT 1")
            sample_row = cursor.fetchone()

            schema_parts.append(f"表 [{table_name}]: {info['description']}")
            schema_parts.append(f"  列: {', '.join(columns)}")
            if sample_row:
                schema_parts.append(f"  示例: {dict(sample_row)}")
        except sqlite3.OperationalError:
            pass

    # 追加 JOIN 关系说明
    schema_parts.append("\n--- 表关联关系 ---")
    schema_parts.append("[orders].[客户ID] -> [customers].[客户ID] (INNER JOIN)")
    schema_parts.append("[orders].[商品ID] -> [products].[商品ID] (INNER JOIN)")
    schema_parts.append("[refunds].[订单ID] -> [orders].[订单ID] (LEFT JOIN, 退款分析)")
    schema_parts.append("[orders] vs [monthly_targets]: 通过 年份+月份+品类 关联(达成率分析)")

    conn.close()
    return "\n".join(schema_parts)


def execute_sql(sql: str, db_path: str = DB_PATH) -> Tuple[List[Dict[str, Any]], List[str]]:
    """执行 SQL 查询，返回结果行和列名"""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(sql)
    columns = [desc[0] for desc in cursor.description] if cursor.description else []
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows, columns


def is_database_ready(db_path: str = DB_PATH) -> bool:
    """检查数据库是否就绪"""
    if not os.path.exists(db_path):
        return False
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    return len(tables) > 0
