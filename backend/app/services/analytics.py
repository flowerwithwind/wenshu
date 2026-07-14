"""数据分析服务 — 多数据源看板聚合统计"""
from __future__ import annotations

from typing import Any

from app.datasources.base import DataSource
from app.datasources.registry import get_datasource
from app.logger import get_logger

logger = get_logger(__name__)


def _empty_chart() -> dict[str, list]:
    return {"labels": [], "data": []}


def _safe_num(val: Any) -> float | int:
    if val is None:
        return 0
    try:
        f = float(val)
        if f == int(f):
            return int(f)
        return round(f, 2)
    except (TypeError, ValueError):
        return 0


def _q(ds: DataSource, name: str) -> str:
    return ds._quote_ident(name)


def _month_expr(ds: DataSource, col: str) -> str:
    dialect = (ds.dialect or "sqlite").lower()
    qcol = _q(ds, col)
    if dialect in ("mysql", "mariadb"):
        return f"DATE_FORMAT({qcol}, '%Y-%m')"
    if dialect in ("postgres", "postgresql"):
        return f"TO_CHAR({qcol}::timestamp, 'YYYY-MM')"
    return f"STRFTIME('%Y-%m', {qcol})"


def _query(ds: DataSource, sql: str) -> list[dict[str, Any]]:
    rows, _ = ds.execute_sql(sql)
    return rows


def _first_val(rows: list[dict[str, Any]], *keys: str) -> Any:
    if not rows:
        return None
    row = rows[0]
    for k in keys:
        if k in row:
            return row[k]
    # 取第一列
    if row:
        return next(iter(row.values()))
    return None


def get_overview_stats(datasource_id: str | None = None) -> dict[str, Any]:
    """
    获取看板概览。
    针对电商演示 Schema（orders/customers/products/refunds）聚合；
    其他数据源若表结构不匹配则返回 0 与空图表，并附 schema 提示。
    """
    ds = get_datasource(datasource_id)
    meta = ds.meta

    stats: dict[str, Any] = {
        "datasource_id": meta.id,
        "datasource_name": meta.name,
        "datasource_type": meta.type,
        "total_revenue": 0,
        "total_orders": 0,
        "total_customers": 0,
        "refund_rate": 0,
        "category_revenue": _empty_chart(),
        "monthly_trend": _empty_chart(),
        "province_distribution": _empty_chart(),
        "schema_ok": False,
        "message": "",
    }

    if not ds.is_ready():
        stats["message"] = f"数据源「{meta.name}」不可用，请先测试连接"
        return stats

    o = _q(ds, "orders")
    c = _q(ds, "customers")
    p = _q(ds, "products")
    r = _q(ds, "refunds")
    col_amt = _q(ds, "订单金额_元")
    col_status = _q(ds, "订单状态")
    col_order_id = _q(ds, "订单ID")
    col_product_id = _q(ds, "商品ID")
    col_category = _q(ds, "品类")
    col_date = _q(ds, "日期")
    col_province = _q(ds, "收货省份")

    try:
        # 探测电商 Schema
        probe = _query(ds, f"SELECT COUNT(*) AS cnt FROM {o}")
        _ = _first_val(probe, "cnt")
        stats["schema_ok"] = True
    except Exception as e:
        logger.info(f"看板 Schema 不兼容 datasource={meta.id}: {e}")
        stats["message"] = (
            f"数据源「{meta.name}」表结构与电商演示看板不匹配"
            "（需要 orders / customers / products / refunds 及中文列名）。"
            "可在智能问数中对该库做自然语言查询。"
        )
        return stats

    try:
        rows = _query(
            ds,
            f"SELECT SUM({col_amt}) AS total FROM {o} WHERE {col_status} = '已完成'",
        )
        stats["total_revenue"] = _safe_num(_first_val(rows, "total", "总销售额"))
    except Exception as e:
        logger.debug(f"total_revenue failed: {e}")

    try:
        rows = _query(ds, f"SELECT COUNT(*) AS total FROM {o}")
        stats["total_orders"] = _safe_num(_first_val(rows, "total", "总订单数"))
    except Exception as e:
        logger.debug(f"total_orders failed: {e}")

    try:
        rows = _query(ds, f"SELECT COUNT(*) AS total FROM {c}")
        stats["total_customers"] = _safe_num(_first_val(rows, "total", "客户数"))
    except Exception as e:
        logger.debug(f"total_customers failed: {e}")

    try:
        rows = _query(
            ds,
            f"SELECT CAST(COUNT(DISTINCT r.{col_order_id}) AS REAL) * 100.0 / "
            f"NULLIF(COUNT(DISTINCT o.{col_order_id}), 0) AS rate "
            f"FROM {o} o LEFT JOIN {r} r ON o.{col_order_id} = r.{col_order_id}",
        )
        stats["refund_rate"] = round(float(_first_val(rows, "rate", "退款率") or 0), 2)
    except Exception as e:
        logger.debug(f"refund_rate failed: {e}")

    try:
        rows = _query(
            ds,
            f"SELECT p.{col_category} AS label, SUM(o.{col_amt}) AS value "
            f"FROM {o} o JOIN {p} p ON o.{col_product_id} = p.{col_product_id} "
            f"WHERE o.{col_status} = '已完成' "
            f"GROUP BY p.{col_category} ORDER BY value DESC",
        )
        stats["category_revenue"] = {
            "labels": [str(r.get("label") or r.get("品类") or "") for r in rows],
            "data": [_safe_num(r.get("value", r.get("销售额"))) for r in rows],
        }
    except Exception as e:
        logger.debug(f"category_revenue failed: {e}")

    try:
        month_expr = _month_expr(ds, "日期")
        rows = _query(
            ds,
            f"SELECT {month_expr} AS label, SUM({col_amt}) AS value "
            f"FROM {o} WHERE {col_status} = '已完成' "
            f"GROUP BY {month_expr} ORDER BY label",
        )
        stats["monthly_trend"] = {
            "labels": [str(r.get("label") or r.get("月") or "") for r in rows],
            "data": [_safe_num(r.get("value", r.get("销售额"))) for r in rows],
        }
    except Exception as e:
        logger.debug(f"monthly_trend failed: {e}")

    try:
        rows = _query(
            ds,
            f"SELECT {col_province} AS label, SUM({col_amt}) AS value "
            f"FROM {o} WHERE {col_status} = '已完成' "
            f"GROUP BY {col_province} ORDER BY value DESC",
        )
        stats["province_distribution"] = {
            "labels": [str(r.get("label") or r.get("收货省份") or "") for r in rows],
            "data": [_safe_num(r.get("value", r.get("销售额"))) for r in rows],
        }
    except Exception as e:
        logger.debug(f"province_distribution failed: {e}")

    if not stats["message"]:
        stats["message"] = f"当前数据源：{meta.name}"

    return stats
