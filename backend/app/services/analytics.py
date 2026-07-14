"""自适应数据分析看板 — 按数据源 Schema 生成 KPI / 图表（结构可不同）"""
from __future__ import annotations

import re
import sqlite3
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
        if abs(f - int(f)) < 1e-9:
            return int(f)
        return round(f, 2)
    except (TypeError, ValueError):
        return 0


def _q(ds: DataSource, name: str) -> str:
    return ds._quote_ident(name)  # noqa: SLF001


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
    if row:
        return next(iter(row.values()))
    return None


def _kpi(key: str, label: str, value: Any, fmt: str = "number", icon: str = "orders") -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "value": value,
        "format": fmt,  # number | currency | percent | text
        "icon": icon,   # revenue | orders | customers | refund | generic
    }


def _chart(
    cid: str,
    title: str,
    chart_type: str,
    labels: list[Any],
    data: list[Any],
    dataset_label: str = "数值",
    wide: bool = False,
) -> dict[str, Any]:
    return {
        "id": cid,
        "title": title,
        "type": chart_type,  # bar | line | pie
        "labels": [str(x) if x is not None else "" for x in labels],
        "data": [_safe_num(x) for x in data],
        "dataset_label": dataset_label,
        "wide": wide,
    }


# ---------- schema introspection ----------

def _list_tables_and_columns(ds: DataSource) -> dict[str, list[str]]:
    """返回 {table: [col, ...]}"""
    result: dict[str, list[str]] = {}
    dialect = (ds.dialect or "sqlite").lower()
    try:
        if ds.meta.type == "sqlite" or dialect == "sqlite":
            path = ds.meta.extra.get("path") or ""
            if not path:
                return result
            conn = sqlite3.connect(path)
            conn.row_factory = sqlite3.Row
            try:
                cur = conn.cursor()
                cur.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name NOT LIKE 'sqlite_%' ORDER BY name"
                )
                tables = [r[0] for r in cur.fetchall()]
                for t in tables:
                    cur.execute(f"PRAGMA table_info([{t}])")
                    result[t] = [r[1] for r in cur.fetchall()]
            finally:
                conn.close()
            return result

        from sqlalchemy import inspect

        eng = ds._engine()  # noqa: SLF001
        insp = inspect(eng)
        for t in insp.get_table_names():
            cols = [c["name"] for c in insp.get_columns(t)]
            result[t] = cols
        return result
    except Exception as e:
        logger.warning(f"introspect schema failed: {e}")
        return result


def _count_table(ds: DataSource, table: str) -> int:
    try:
        rows = _query(ds, f"SELECT COUNT(*) AS cnt FROM {_q(ds, table)}")
        return int(_safe_num(_first_val(rows, "cnt")))
    except Exception:
        return 0


def _is_numeric_name(col: str) -> bool:
    c = col.lower()
    return bool(
        re.search(
            r"(amount|price|cost|revenue|sales|total|sum|qty|quantity|count|rate|"
            r"score|value|miles|hours|gallon|mpg|fee|charge|balance|gmv|num|n_)",
            c,
        )
    )


def _is_categorical_name(col: str) -> bool:
    c = col.lower()
    if _is_numeric_name(col) or _is_date_name(col) or c.endswith("_id") or c == "id":
        return False
    return bool(
        re.search(
            r"(status|type|category|state|city|province|region|name|gender|"
            r"level|mode|method|specialization|department|class|brand|role|flag)",
            c,
        )
    ) or (not c.endswith("_id") and len(c) < 40)


def _is_date_name(col: str) -> bool:
    c = col.lower()
    return bool(re.search(r"(date|time|month|year|day|created|updated|dispatch)", c))


def _pick_col(cols: list[str], prefer: list[str]) -> str | None:
    lower_map = {c.lower(): c for c in cols}
    for p in prefer:
        if p.lower() in lower_map:
            return lower_map[p.lower()]
    for p in prefer:
        for c in cols:
            if p.lower() in c.lower():
                return c
    return None


def _group_count(
    ds: DataSource,
    table: str,
    cat_col: str,
    limit: int = 8,
) -> tuple[list[str], list[Any]]:
    qt, qc = _q(ds, table), _q(ds, cat_col)
    sql = (
        f"SELECT {qc} AS label, COUNT(*) AS value FROM {qt} "
        f"GROUP BY {qc} ORDER BY value DESC LIMIT {limit}"
    )
    rows = _query(ds, sql)
    labels = [str(r.get("label") if r.get("label") is not None else "") for r in rows]
    data = [_safe_num(r.get("value")) for r in rows]
    return labels, data


def _group_sum(
    ds: DataSource,
    table: str,
    cat_col: str,
    num_col: str,
    limit: int = 8,
) -> tuple[list[str], list[Any]]:
    qt, qc, qn = _q(ds, table), _q(ds, cat_col), _q(ds, num_col)
    sql = (
        f"SELECT {qc} AS label, SUM({qn}) AS value FROM {qt} "
        f"GROUP BY {qc} ORDER BY value DESC LIMIT {limit}"
    )
    rows = _query(ds, sql)
    return (
        [str(r.get("label") if r.get("label") is not None else "") for r in rows],
        [_safe_num(r.get("value")) for r in rows],
    )


def _month_trend(
    ds: DataSource,
    table: str,
    date_col: str,
    num_col: str | None = None,
    limit: int = 24,
) -> tuple[list[str], list[Any]]:
    qt = _q(ds, table)
    month = _month_expr(ds, date_col)
    if num_col:
        qn = _q(ds, num_col)
        sql = (
            f"SELECT {month} AS label, SUM({qn}) AS value FROM {qt} "
            f"WHERE {month} IS NOT NULL GROUP BY {month} ORDER BY label LIMIT {limit}"
        )
    else:
        sql = (
            f"SELECT {month} AS label, COUNT(*) AS value FROM {qt} "
            f"WHERE {month} IS NOT NULL GROUP BY {month} ORDER BY label LIMIT {limit}"
        )
    rows = _query(ds, sql)
    return (
        [str(r.get("label") or "") for r in rows],
        [_safe_num(r.get("value")) for r in rows],
    )


# ---------- domain builders ----------

def _build_ecommerce(ds: DataSource) -> dict[str, Any] | None:
    schema = _list_tables_and_columns(ds)
    if "orders" not in schema:
        return None
    ocols = schema["orders"]
    # 中文电商列
    if "订单金额_元" not in ocols and "订单金额" not in ocols:
        # 英文 ecommerce 也可尝试
        if not any("amount" in c.lower() or "price" in c.lower() for c in ocols):
            return None

    o = _q(ds, "orders")
    kpis: list[dict[str, Any]] = []
    charts: list[dict[str, Any]] = []

    # 中文优先
    col_amt = _pick_col(ocols, ["订单金额_元", "订单金额", "实付金额_元", "price", "amount", "order_amount"])
    col_status = _pick_col(ocols, ["订单状态", "order_status", "status"])
    col_date = _pick_col(ocols, ["日期", "order_date", "order_purchase_timestamp", "created_at", "date"])
    col_province = _pick_col(ocols, ["收货省份", "province", "customer_state", "state"])

    try:
        if col_amt and col_status and "已完成" in str(col_status):
            pass
        if col_amt:
            if col_status:
                # try completed filter variants
                total = 0
                for st in ("已完成", "delivered", "completed", "Completed"):
                    try:
                        rows = _query(
                            ds,
                            f"SELECT SUM({_q(ds, col_amt)}) AS total FROM {o} "
                            f"WHERE {_q(ds, col_status)} = '{st}'",
                        )
                        total = _safe_num(_first_val(rows, "total"))
                        if total:
                            break
                    except Exception:
                        continue
                if not total:
                    rows = _query(ds, f"SELECT SUM({_q(ds, col_amt)}) AS total FROM {o}")
                    total = _safe_num(_first_val(rows, "total"))
            else:
                rows = _query(ds, f"SELECT SUM({_q(ds, col_amt)}) AS total FROM {o}")
                total = _safe_num(_first_val(rows, "total"))
            kpis.append(_kpi("revenue", "总销售额", total, "currency", "revenue"))
    except Exception as e:
        logger.debug(f"ecom revenue: {e}")

    try:
        rows = _query(ds, f"SELECT COUNT(*) AS total FROM {o}")
        kpis.append(_kpi("orders", "订单数", _safe_num(_first_val(rows, "total")), "number", "orders"))
    except Exception:
        pass

    if "customers" in schema:
        try:
            rows = _query(ds, f"SELECT COUNT(*) AS total FROM {_q(ds, 'customers')}")
            kpis.append(
                _kpi("customers", "客户数", _safe_num(_first_val(rows, "total")), "number", "customers")
            )
        except Exception:
            pass

    if "refunds" in schema and "订单ID" in schema.get("orders", []):
        try:
            rows = _query(
                ds,
                "SELECT CAST(COUNT(DISTINCT r.[订单ID]) AS REAL) * 100.0 / "
                "NULLIF(COUNT(DISTINCT o.[订单ID]), 0) AS rate "
                "FROM [orders] o LEFT JOIN [refunds] r ON o.[订单ID] = r.[订单ID]",
            )
            kpis.append(
                _kpi("refund_rate", "退款率", round(float(_first_val(rows, "rate") or 0), 2), "percent", "refund")
            )
        except Exception:
            pass

    # charts
    if "products" in schema and col_amt:
        pcols = schema["products"]
        cat = _pick_col(pcols, ["品类", "product_category_name", "category"])
        pid_o = _pick_col(ocols, ["商品ID", "product_id"])
        pid_p = _pick_col(pcols, ["商品ID", "product_id"])
        if cat and pid_o and pid_p:
            try:
                sql = (
                    f"SELECT p.{_q(ds, cat)} AS label, SUM(o.{_q(ds, col_amt)}) AS value "
                    f"FROM {o} o JOIN {_q(ds, 'products')} p ON o.{_q(ds, pid_o)} = p.{_q(ds, pid_p)} "
                    f"GROUP BY p.{_q(ds, cat)} ORDER BY value DESC LIMIT 10"
                )
                rows = _query(ds, sql)
                charts.append(
                    _chart(
                        "category",
                        "品类/分类销售额",
                        "bar",
                        [r.get("label") for r in rows],
                        [r.get("value") for r in rows],
                        "销售额",
                        wide=True,
                    )
                )
            except Exception as e:
                logger.debug(f"ecom category chart: {e}")

    if col_date and col_amt:
        try:
            labels, data = _month_trend(ds, "orders", col_date, col_amt)
            if labels:
                charts.append(_chart("trend", "月度销售趋势", "line", labels, data, "销售额"))
        except Exception as e:
            logger.debug(f"ecom trend: {e}")

    if col_province and col_amt:
        try:
            labels, data = _group_sum(ds, "orders", col_province, col_amt, 10)
            if labels:
                charts.append(_chart("geo", "地区销售分布", "pie", labels, data, "销售额"))
        except Exception as e:
            logger.debug(f"ecom geo: {e}")

    if not kpis:
        return None
    return {
        "profile": "ecommerce",
        "profile_label": "电商分析",
        "kpis": kpis[:4],
        "charts": charts[:4],
        "message": "电商类 Schema 自适应看板",
    }


def _build_hospital(ds: DataSource, schema: dict[str, list[str]]) -> dict[str, Any] | None:
    tables = set(schema.keys())
    if not {"patients", "doctors", "appointments"}.issubset(tables) and not (
        "patients" in tables and "appointments" in tables
    ):
        # soft detect
        if "patients" not in tables:
            return None
        if not any(t in tables for t in ("appointments", "doctors", "billing", "treatments")):
            return None

    kpis: list[dict[str, Any]] = []
    charts: list[dict[str, Any]] = []

    for t, label, icon in (
        ("patients", "患者数", "customers"),
        ("doctors", "医生数", "orders"),
        ("appointments", "预约数", "revenue"),
        ("billing", "账单数", "refund"),
        ("treatments", "诊疗记录", "generic"),
    ):
        if t in schema:
            kpis.append(_kpi(t, label, _count_table(ds, t), "number", icon))
        if len(kpis) >= 4:
            break

    if "appointments" in schema and "doctors" in schema:
        acols, dcols = schema["appointments"], schema["doctors"]
        doc_fk = _pick_col(acols, ["doctor_id", "医生ID"])
        doc_pk = _pick_col(dcols, ["doctor_id", "医生ID", "id"])
        spec = _pick_col(dcols, ["specialization", "specialty", "department", "科室"])
        if doc_fk and doc_pk and spec:
            try:
                sql = (
                    f"SELECT d.{_q(ds, spec)} AS label, COUNT(*) AS value "
                    f"FROM {_q(ds, 'appointments')} a "
                    f"JOIN {_q(ds, 'doctors')} d ON a.{_q(ds, doc_fk)} = d.{_q(ds, doc_pk)} "
                    f"GROUP BY d.{_q(ds, spec)} ORDER BY value DESC LIMIT 8"
                )
                rows = _query(ds, sql)
                charts.append(
                    _chart(
                        "dept",
                        "各专科预约量",
                        "bar",
                        [r.get("label") for r in rows],
                        [r.get("value") for r in rows],
                        "预约数",
                        wide=True,
                    )
                )
            except Exception as e:
                logger.debug(f"hospital dept: {e}")

    if "appointments" in schema:
        acols = schema["appointments"]
        status = _pick_col(acols, ["status", "appointment_status", "状态"])
        if status:
            try:
                labels, data = _group_count(ds, "appointments", status)
                charts.append(_chart("appt_status", "预约状态分布", "pie", labels, data, "数量"))
            except Exception as e:
                logger.debug(f"hospital status: {e}")
        date_c = _pick_col(acols, ["appointment_date", "date", "created_at", "预约日期"])
        if date_c:
            try:
                labels, data = _month_trend(ds, "appointments", date_c)
                if labels:
                    charts.append(_chart("appt_trend", "预约量趋势", "line", labels, data, "预约数"))
            except Exception as e:
                logger.debug(f"hospital trend: {e}")

    if "billing" in schema:
        bcols = schema["billing"]
        amt = _pick_col(bcols, ["amount", "total", "cost", "charge", "金额"])
        if amt:
            try:
                rows = _query(ds, f"SELECT SUM({_q(ds, amt)}) AS total FROM {_q(ds, 'billing')}")
                total = _safe_num(_first_val(rows, "total"))
                if len(kpis) < 4:
                    kpis.append(_kpi("billing_sum", "账单总额", total, "currency", "revenue"))
                st = _pick_col(bcols, ["status", "payment_status"])
                if st:
                    labels, data = _group_sum(ds, "billing", st, amt)
                    charts.append(_chart("bill_status", "账单金额 by 状态", "bar", labels, data, "金额"))
            except Exception as e:
                logger.debug(f"hospital billing: {e}")

    if not kpis:
        return None
    return {
        "profile": "hospital",
        "profile_label": "医院运营",
        "kpis": kpis[:4],
        "charts": charts[:4],
        "message": "医院类 Schema 自适应看板",
    }


def _build_logistics(ds: DataSource, schema: dict[str, list[str]]) -> dict[str, Any] | None:
    tables = set(schema.keys())
    if "trips" not in tables and "loads" not in tables:
        return None
    if not any(t in tables for t in ("drivers", "trucks", "routes", "loads", "trips")):
        return None

    kpis: list[dict[str, Any]] = []
    charts: list[dict[str, Any]] = []

    for t, label, icon in (
        ("trips", "行程数", "orders"),
        ("loads", "运单数", "revenue"),
        ("drivers", "司机数", "customers"),
        ("trucks", "车辆数", "generic"),
        ("customers", "客户数", "customers"),
    ):
        if t in schema:
            kpis.append(_kpi(t, label, _count_table(ds, t), "number", icon))
        if len(kpis) >= 4:
            break

    if "trips" in schema:
        tcols = schema["trips"]
        status = _pick_col(tcols, ["trip_status", "status"])
        if status:
            try:
                labels, data = _group_count(ds, "trips", status)
                charts.append(_chart("trip_status", "行程状态分布", "pie", labels, data, "数量"))
            except Exception as e:
                logger.debug(f"logistics status: {e}")
        miles = _pick_col(tcols, ["actual_distance_miles", "distance", "miles"])
        date_c = _pick_col(tcols, ["dispatch_date", "date", "created_at"])
        if date_c:
            try:
                labels, data = _month_trend(ds, "trips", date_c, miles if miles else None)
                if labels:
                    title = "月度里程" if miles else "月度行程量"
                    charts.append(
                        _chart("trip_trend", title, "line", labels, data, "里程" if miles else "行程数")
                    )
            except Exception as e:
                logger.debug(f"logistics trend: {e}")
        if miles and status:
            try:
                labels, data = _group_sum(ds, "trips", status, miles)
                charts.append(
                    _chart("miles_by_status", "各状态里程合计", "bar", labels, data, "英里", wide=True)
                )
            except Exception as e:
                logger.debug(f"logistics miles: {e}")

    if "drivers" in schema and "trips" in schema:
        dcols, tcols = schema["drivers"], schema["trips"]
        dfk = _pick_col(tcols, ["driver_id"])
        dpk = _pick_col(dcols, ["driver_id", "id"])
        # any categorical on drivers
        cats = [c for c in dcols if _is_categorical_name(c)]
        if dfk and dpk and cats:
            cat = cats[0]
            try:
                sql = (
                    f"SELECT d.{_q(ds, cat)} AS label, COUNT(*) AS value "
                    f"FROM {_q(ds, 'trips')} t "
                    f"JOIN {_q(ds, 'drivers')} d ON t.{_q(ds, dfk)} = d.{_q(ds, dpk)} "
                    f"GROUP BY d.{_q(ds, cat)} ORDER BY value DESC LIMIT 8"
                )
                rows = _query(ds, sql)
                if rows:
                    charts.append(
                        _chart(
                            "by_driver_dim",
                            f"行程量 by 司机·{cat}",
                            "bar",
                            [r.get("label") for r in rows],
                            [r.get("value") for r in rows],
                            "行程数",
                        )
                    )
            except Exception as e:
                logger.debug(f"logistics driver dim: {e}")

    if not kpis:
        return None
    return {
        "profile": "logistics",
        "profile_label": "物流运营",
        "kpis": kpis[:4],
        "charts": charts[:4],
        "message": "物流类 Schema 自适应看板",
    }


def _build_generic(ds: DataSource, schema: dict[str, list[str]]) -> dict[str, Any]:
    """通用策略：表行数 KPI + 大表分类统计/趋势。"""
    if not schema:
        return {
            "profile": "empty",
            "profile_label": "空库",
            "kpis": [],
            "charts": [],
            "message": "当前数据源没有可分析的表，请先导入数据",
        }

    # table sizes
    sizes: list[tuple[str, int]] = []
    for t in schema:
        sizes.append((t, _count_table(ds, t)))
    sizes.sort(key=lambda x: x[1], reverse=True)

    kpis: list[dict[str, Any]] = []
    icons = ["orders", "customers", "revenue", "generic"]
    for i, (t, n) in enumerate(sizes[:4]):
        kpis.append(_kpi(f"tbl_{t}", f"表 {t}", n, "number", icons[i % len(icons)]))

    charts: list[dict[str, Any]] = []
    # for top 2 non-empty tables build a chart
    for t, n in sizes[:3]:
        if n <= 0:
            continue
        cols = schema[t]
        cats = [c for c in cols if _is_categorical_name(c)]
        nums = [c for c in cols if _is_numeric_name(c)]
        dates = [c for c in cols if _is_date_name(c)]

        if cats:
            try:
                if nums:
                    labels, data = _group_sum(ds, t, cats[0], nums[0], 8)
                    title = f"{t}: {nums[0]} by {cats[0]}"
                    charts.append(_chart(f"{t}_bar", title, "bar", labels, data, nums[0], wide=len(charts) == 0))
                else:
                    labels, data = _group_count(ds, t, cats[0], 8)
                    title = f"{t}: 数量 by {cats[0]}"
                    ctype = "pie" if len(charts) >= 1 else "bar"
                    charts.append(
                        _chart(f"{t}_{ctype}", title, ctype, labels, data, "数量", wide=ctype == "bar" and not charts)
                    )
            except Exception as e:
                logger.debug(f"generic chart {t}: {e}")

        if dates and len(charts) < 4:
            try:
                labels, data = _month_trend(ds, t, dates[0], nums[0] if nums else None)
                if labels:
                    charts.append(
                        _chart(
                            f"{t}_trend",
                            f"{t} 时间趋势",
                            "line",
                            labels,
                            data,
                            nums[0] if nums else "计数",
                        )
                    )
            except Exception as e:
                logger.debug(f"generic trend {t}: {e}")

        if len(charts) >= 4:
            break

    # table size bar
    if sizes and len(charts) < 4:
        charts.append(
            _chart(
                "table_sizes",
                "各表行数",
                "bar",
                [t for t, _ in sizes[:12]],
                [n for _, n in sizes[:12]],
                "行数",
                wide=True,
            )
        )

    return {
        "profile": "generic",
        "profile_label": "通用概览",
        "kpis": kpis[:4],
        "charts": charts[:4],
        "message": "已按表结构自动生成通用看板",
    }


def _tables_summary(schema: dict[str, list[str]], ds: DataSource) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for t, cols in sorted(schema.items(), key=lambda x: x[0]):
        out.append({"name": t, "columns": len(cols), "rows": _count_table(ds, t)})
    out.sort(key=lambda x: x["rows"], reverse=True)
    return out[:30]


def get_overview_stats(datasource_id: str | None = None) -> dict[str, Any]:
    """
    自适应看板：
    1) 识别电商 / 医院 / 物流等模板
    2) 否则通用 introspect 生成 KPI + 图表
    返回统一结构 kpis[] + charts[]，并保留兼容字段。
    """
    ds = get_datasource(datasource_id)
    meta = ds.meta

    base: dict[str, Any] = {
        "datasource_id": meta.id,
        "datasource_name": meta.name,
        "datasource_type": meta.type,
        "schema_ok": False,
        "profile": "unknown",
        "profile_label": "",
        "message": "",
        "kpis": [],
        "charts": [],
        "tables_summary": [],
        # 兼容旧前端字段
        "total_revenue": 0,
        "total_orders": 0,
        "total_customers": 0,
        "refund_rate": 0,
        "category_revenue": _empty_chart(),
        "monthly_trend": _empty_chart(),
        "province_distribution": _empty_chart(),
    }

    if not ds.is_ready():
        base["message"] = f"数据源「{meta.name}」不可用或尚无表，请先导入数据并测试连接"
        return base

    schema = _list_tables_and_columns(ds)
    if not schema:
        base["message"] = f"数据源「{meta.name}」未检测到业务表，请先导入 CSV/Excel"
        return base

    base["tables_summary"] = _tables_summary(schema, ds)
    base["schema_ok"] = True

    built: dict[str, Any] | None = None
    # domain-specific first
    try:
        built = _build_ecommerce(ds)
    except Exception as e:
        logger.debug(f"ecommerce profile fail: {e}")
    if not built:
        try:
            built = _build_hospital(ds, schema)
        except Exception as e:
            logger.debug(f"hospital profile fail: {e}")
    if not built:
        try:
            built = _build_logistics(ds, schema)
        except Exception as e:
            logger.debug(f"logistics profile fail: {e}")
    if not built:
        built = _build_generic(ds, schema)

    base["profile"] = built.get("profile", "generic")
    base["profile_label"] = built.get("profile_label", "")
    base["message"] = built.get("message") or f"当前数据源：{meta.name}"
    base["kpis"] = built.get("kpis") or []
    base["charts"] = built.get("charts") or []

    # 填充兼容字段（尽量映射）
    for k in base["kpis"]:
        key = k.get("key")
        val = k.get("value")
        if key in ("revenue", "billing_sum") or k.get("format") == "currency":
            if not base["total_revenue"]:
                base["total_revenue"] = val
        if key in ("orders", "appointments", "trips", "loads"):
            if not base["total_orders"]:
                base["total_orders"] = val
        if key in ("customers", "patients", "drivers"):
            if not base["total_customers"]:
                base["total_customers"] = val
        if key == "refund_rate" or k.get("format") == "percent":
            if key == "refund_rate":
                base["refund_rate"] = val

    # map first charts into legacy slots for older UI
    for ch in base["charts"]:
        payload = {"labels": ch.get("labels") or [], "data": ch.get("data") or []}
        if ch.get("type") == "bar" and not base["category_revenue"]["labels"]:
            base["category_revenue"] = payload
        elif ch.get("type") == "line" and not base["monthly_trend"]["labels"]:
            base["monthly_trend"] = payload
        elif ch.get("type") == "pie" and not base["province_distribution"]["labels"]:
            base["province_distribution"] = payload

    return base
