"""将 Olist 电商多表 CSV 导入 MySQL（复杂 JOIN 场景）"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

BACKEND = Path(__file__).resolve().parent.parent
TMP = BACKEND / "data" / "_kaggle_tmp" / "olist"
DB_NAME = "olist_ecommerce"
import os

USER = os.getenv("MYSQL_USER", "root")
PASSWORD = os.getenv("MYSQL_PASSWORD", "")
HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
PORT = int(os.getenv("MYSQL_PORT", "3306"))


def main() -> int:
    if not TMP.exists():
        print(f"CSV 目录不存在: {TMP}", flush=True)
        return 1

    root_url = f"mysql+pymysql://{USER}:{PASSWORD}@{HOST}:{PORT}/?charset=utf8mb4"
    engine_root = create_engine(root_url, pool_pre_ping=True)
    with engine_root.begin() as conn:
        conn.execute(
            text(
                f"CREATE DATABASE IF NOT EXISTS {DB_NAME} "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        )
    print(f"database ready: {DB_NAME}", flush=True)

    db_url = (
        f"mysql+pymysql://{USER}:{PASSWORD}@{HOST}:{PORT}/{DB_NAME}?charset=utf8mb4"
    )
    engine = create_engine(db_url, pool_pre_ping=True)

    mapping = {
        "customers": "olist_customers_dataset.csv",
        "orders": "olist_orders_dataset.csv",
        "order_items": "olist_order_items_dataset.csv",
        "products": "olist_products_dataset.csv",
        "sellers": "olist_sellers_dataset.csv",
        "order_payments": "olist_order_payments_dataset.csv",
        "order_reviews": "olist_order_reviews_dataset.csv",
        "product_category_translation": "product_category_name_translation.csv",
    }

    for table, fname in mapping.items():
        path = TMP / fname
        if not path.exists():
            print(f"missing file: {path}", flush=True)
            return 1
        t0 = time.time()
        print(f"import {table} <- {fname}", flush=True)
        first = True
        total = 0
        for chunk in pd.read_csv(path, chunksize=15000, low_memory=False):
            chunk.to_sql(
                table,
                engine,
                if_exists="replace" if first else "append",
                index=False,
                method="multi",
                chunksize=500,
            )
            first = False
            total += len(chunk)
            print(f"  ... {total} rows", flush=True)
        print(f"  done rows={total} in {time.time() - t0:.1f}s", flush=True)

    idx_sqls = [
        "CREATE INDEX idx_customers_id ON customers (customer_id(64))",
        "CREATE INDEX idx_orders_id ON orders (order_id(64))",
        "CREATE INDEX idx_orders_customer ON orders (customer_id(64))",
        "CREATE INDEX idx_orders_status ON orders (order_status(32))",
        "CREATE INDEX idx_items_order ON order_items (order_id(64))",
        "CREATE INDEX idx_items_product ON order_items (product_id(64))",
        "CREATE INDEX idx_items_seller ON order_items (seller_id(64))",
        "CREATE INDEX idx_products_id ON products (product_id(64))",
        "CREATE INDEX idx_sellers_id ON sellers (seller_id(64))",
        "CREATE INDEX idx_payments_order ON order_payments (order_id(64))",
        "CREATE INDEX idx_reviews_order ON order_reviews (order_id(64))",
    ]
    with engine.begin() as conn:
        for sql in idx_sqls:
            try:
                conn.execute(text(sql))
                print(f"index ok: {sql}", flush=True)
            except Exception as e:
                print(f"index skip: {e}", flush=True)

    with engine.connect() as conn:
        for t in mapping:
            n = conn.execute(text(f"SELECT COUNT(*) FROM `{t}`")).scalar()
            print(f"count {t}={n}", flush=True)
        q = """
        SELECT p.product_category_name AS category,
               COUNT(*) AS order_lines,
               ROUND(SUM(i.price), 2) AS gmv
        FROM order_items i
        JOIN products p ON i.product_id = p.product_id
        JOIN orders o ON i.order_id = o.order_id
        WHERE o.order_status = 'delivered'
        GROUP BY p.product_category_name
        ORDER BY gmv DESC
        LIMIT 5
        """
        rows = conn.execute(text(q)).mappings().all()
        print("top categories:", flush=True)
        for r in rows:
            print(dict(r), flush=True)

    print("IMPORT_DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
