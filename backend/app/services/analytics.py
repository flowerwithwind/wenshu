"""数据分析服务 — 聚合统计、热门查询记录"""
from __future__ import annotations

from app.nl2sql.database import get_connection

DB_PATH: str | None = None  # 使用默认路径


def _query(sql: str) -> tuple[list[str], list[dict]]:
    """执行单条查询并返回结果"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(sql)
    columns: list[str] = [desc[0] for desc in cursor.description]
    rows: list[dict] = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return columns, rows


def get_overview_stats() -> dict:
    """获取概览统计"""
    stats: dict = {}

    # 总销售额
    try:
        _, rows = _query(
            "SELECT SUM([订单金额_元]) AS 总销售额 FROM [orders] WHERE [订单状态] = '已完成'"
        )
        stats["total_revenue"] = rows[0]["总销售额"] if rows else 0
    except Exception:
        stats["total_revenue"] = 0

    # 总订单数
    try:
        _, rows = _query("SELECT COUNT(*) AS 总订单数 FROM [orders]")
        stats["total_orders"] = rows[0]["总订单数"] if rows else 0
    except Exception:
        stats["total_orders"] = 0

    # 客户数
    try:
        _, rows = _query("SELECT COUNT(*) AS 客户数 FROM [customers]")
        stats["total_customers"] = rows[0]["客户数"] if rows else 0
    except Exception:
        stats["total_customers"] = 0

    # 退款率
    try:
        _, rows = _query(
            "SELECT CAST(COUNT(DISTINCT [r].[订单ID]) AS REAL) * 100.0 / "
            "NULLIF(COUNT(DISTINCT [o].[订单ID]), 0) AS 退款率 "
            "FROM [orders] [o] LEFT JOIN [refunds] [r] ON [o].[订单ID] = [r].[订单ID]"
        )
        stats["refund_rate"] = round(rows[0]["退款率"], 2) if rows else 0
    except Exception:
        stats["refund_rate"] = 0

    # 各品类销售额排名
    try:
        _, rows = _query(
            "SELECT [p].[品类], SUM([o].[订单金额_元]) AS 销售额 "
            "FROM [orders] [o] JOIN [products] [p] ON [o].[商品ID] = [p].[商品ID] "
            "WHERE [o].[订单状态] = '已完成' GROUP BY [p].[品类] ORDER BY 销售额 DESC"
        )
        stats["category_revenue"] = {
            "labels": [r["品类"] for r in rows],
            "data": [r["销售额"] for r in rows],
        }
    except Exception:
        stats["category_revenue"] = {"labels": [], "data": []}

    # 月度销售趋势
    try:
        _, rows = _query(
            "SELECT STRFTIME('%Y-%m', [日期]) AS 月, SUM([订单金额_元]) AS 销售额 "
            "FROM [orders] WHERE [订单状态] = '已完成' GROUP BY 月 ORDER BY 月"
        )
        stats["monthly_trend"] = {
            "labels": [r["月"] for r in rows],
            "data": [r["销售额"] for r in rows],
        }
    except Exception:
        stats["monthly_trend"] = {"labels": [], "data": []}

    # 省份销售分布
    try:
        _, rows = _query(
            "SELECT [收货省份], SUM([订单金额_元]) AS 销售额 "
            "FROM [orders] WHERE [订单状态] = '已完成' GROUP BY [收货省份] ORDER BY 销售额 DESC"
        )
        stats["province_distribution"] = {
            "labels": [r["收货省份"] for r in rows],
            "data": [r["销售额"] for r in rows],
        }
    except Exception:
        stats["province_distribution"] = {"labels": [], "data": []}

    return stats
