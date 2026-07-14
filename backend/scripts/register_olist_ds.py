"""注册 Olist MySQL 为 SmartQA 数据源并做连通性/复杂 SQL 验证"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# 保证可 import app
BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from app.datasources.manager import create_record, list_datasource_records, public_record
from app.datasources.registry import get_datasource, invalidate_datasource_cache


def main() -> int:
    # 避免重复注册同名库
    for r in list_datasource_records():
        if r.get("name") == "Olist 巴西电商 (MySQL)" or (
            r.get("type") == "mysql" and r.get("database") == "olist_ecommerce"
        ):
            print("already registered:", public_record(r))
            ds_id = r["id"]
            break
    else:
        import os

        password = os.getenv("MYSQL_PASSWORD", "")
        if not password:
            print("请设置环境变量 MYSQL_PASSWORD 后再注册", file=sys.stderr)
            return 1
        rec = create_record(
            {
                "name": "Olist 巴西电商 (MySQL)",
                "type": "mysql",
                "description": (
                    "Kaggle Brazilian E-Commerce (Olist) 多表数据集："
                    "customers/orders/order_items/products/sellers/"
                    "order_payments/order_reviews + category translation。"
                    "适合多表 JOIN、聚合与漏斗分析。"
                ),
                "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
                "port": int(os.getenv("MYSQL_PORT", "3306")),
                "database": "olist_ecommerce",
                "username": os.getenv("MYSQL_USER", "root"),
                "password": password,
                "is_default": False,
            }
        )
        ds_id = rec["id"]
        print("created datasource:", json.dumps(public_record(rec), ensure_ascii=False, indent=2))

    invalidate_datasource_cache(ds_id)
    ds = get_datasource(ds_id)
    test = ds.test_connection()
    print("test_connection:", test)
    if not test.get("ok"):
        return 1

    schema = ds.get_schema_info()
    print("schema_preview:\n", schema[:1200], "...\n")

    # 复杂查询 1：品类 GMV 排名（3 表 JOIN + 聚合）
    sql1 = """
    SELECT p.product_category_name AS category,
           COUNT(*) AS lines_cnt,
           ROUND(SUM(i.price), 2) AS gmv
    FROM order_items i
    JOIN products p ON i.product_id = p.product_id
    JOIN orders o ON i.order_id = o.order_id
    WHERE o.order_status = 'delivered'
    GROUP BY p.product_category_name
    ORDER BY gmv DESC
    LIMIT 5
    """
    rows, cols = ds.execute_sql(sql1)
    print("complex_sql1 cols:", cols)
    print("complex_sql1 rows:", rows)

    # 复杂查询 2：支付方式 × 订单状态
    sql2 = """
    SELECT pay.payment_type, o.order_status,
           COUNT(DISTINCT o.order_id) AS orders_cnt,
           ROUND(SUM(pay.payment_value), 2) AS pay_sum
    FROM order_payments pay
    JOIN orders o ON pay.order_id = o.order_id
    GROUP BY pay.payment_type, o.order_status
    ORDER BY pay_sum DESC
    LIMIT 8
    """
    rows2, cols2 = ds.execute_sql(sql2)
    print("complex_sql2 cols:", cols2)
    print("complex_sql2 sample:", rows2[:5])

    print("VERIFY_OK ds_id=", ds_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
