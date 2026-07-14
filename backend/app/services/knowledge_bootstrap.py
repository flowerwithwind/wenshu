"""
数据源知识库自动初始化
- P0 规则引擎：导入后立即生成 schema / few-shot / 同义词 / 关联
- P1 可选 LLM 增强：用户模型生成业务示例，经 SQL/列名校验后合并
"""
from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

from app.datasources.base import DataSource
from app.datasources.registry import get_datasource
from app.datasources.safety import validate_sql_safety
from app.datasources.sqlite_ds import BUILTIN_SQLITE_ID
from app.logger import get_logger
from app.services.knowledge_manager import load_knowledge, save_knowledge

logger = get_logger(__name__)


def _q(ds: DataSource, name: str) -> str:
    return ds._quote_ident(name)  # noqa: SLF001


def _list_schema(ds: DataSource) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    dialect = (ds.dialect or "sqlite").lower()
    try:
        if ds.meta.type == "sqlite" or dialect == "sqlite":
            path = ds.meta.extra.get("path") or ""
            if not path:
                return result
            conn = sqlite3.connect(path)
            try:
                cur = conn.cursor()
                cur.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name NOT LIKE 'sqlite_%' ORDER BY name"
                )
                for (t,) in cur.fetchall():
                    cur.execute(f"PRAGMA table_info([{t}])")
                    result[t] = [r[1] for r in cur.fetchall()]
            finally:
                conn.close()
            return result
        from sqlalchemy import inspect

        eng = ds._engine()  # noqa: SLF001
        insp = inspect(eng)
        for t in insp.get_table_names():
            result[t] = [c["name"] for c in insp.get_columns(t)]
        return result
    except Exception as e:
        logger.warning(f"bootstrap schema introspect failed: {e}")
        return result


def _is_id_col(col: str) -> bool:
    c = col.lower()
    return c == "id" or c.endswith("_id") or c.endswith("id") and len(c) > 2


def _is_cat_col(col: str) -> bool:
    c = col.lower()
    if _is_id_col(col):
        return False
    return bool(
        re.search(
            r"(status|type|category|state|city|province|region|gender|level|"
            r"method|mode|specialization|department|brand|role|name|flag)",
            c,
        )
    )


def _is_date_col(col: str) -> bool:
    c = col.lower()
    return bool(re.search(r"(date|time|month|year|created|updated|dispatch)", c))


def _is_num_col(col: str) -> bool:
    c = col.lower()
    return bool(
        re.search(
            r"(amount|price|cost|revenue|sales|total|sum|qty|quantity|count|"
            r"score|value|miles|hours|gallon|mpg|fee|charge|gmv|num)",
            c,
        )
    )


def _humanize(name: str) -> str:
    s = re.sub(r"[_\-]+", " ", name).strip()
    # simple Chinese hints
    mapping = {
        "status": "状态",
        "type": "类型",
        "category": "分类",
        "name": "名称",
        "date": "日期",
        "amount": "金额",
        "price": "价格",
        "customer": "客户",
        "order": "订单",
        "product": "商品",
        "doctor": "医生",
        "patient": "患者",
        "trip": "行程",
        "load": "运单",
        "driver": "司机",
        "truck": "车辆",
    }
    lower = name.lower()
    for k, v in mapping.items():
        if k in lower:
            return f"{v}({name})"
    return s or name


def _infer_fks(schema: dict[str, list[str]]) -> list[dict[str, str]]:
    """启发式：table.foo_id → foos.id / foo.id / foos.foo_id"""
    fks: list[dict[str, str]] = []
    tables = list(schema.keys())
    table_set = {t.lower(): t for t in tables}
    for t, cols in schema.items():
        for col in cols:
            cl = col.lower()
            if not cl.endswith("_id") or cl == "id":
                continue
            base = cl[:-3]  # strip _id
            candidates = [
                base,
                base + "s",
                base + "es",
                base[:-1] + "ies" if base.endswith("y") else "",
            ]
            for cand in candidates:
                if not cand or cand not in table_set:
                    continue
                target = table_set[cand]
                tcols = [c.lower() for c in schema[target]]
                # prefer same col name, else id
                if cl in tcols:
                    pk = next(c for c in schema[target] if c.lower() == cl)
                elif "id" in tcols:
                    pk = next(c for c in schema[target] if c.lower() == "id")
                else:
                    continue
                fks.append(
                    {
                        "from_table": t,
                        "from_column": col,
                        "to_table": target,
                        "to_column": pk,
                    }
                )
                break
    return fks


def _ident_sql(ds: DataSource, table: str, col: str | None = None) -> str:
    if col is None:
        return _q(ds, table)
    return f"{_q(ds, table)}.{_q(ds, col)}" if False else f"{_q(ds, col)}"


def _sql_count(ds: DataSource, table: str) -> str:
    return f"SELECT COUNT(*) AS cnt FROM {_q(ds, table)}"


def _sql_group(ds: DataSource, table: str, cat: str) -> str:
    return (
        f"SELECT {_q(ds, cat)} AS label, COUNT(*) AS cnt "
        f"FROM {_q(ds, table)} GROUP BY {_q(ds, cat)} "
        f"ORDER BY cnt DESC LIMIT 10"
    )


def _sql_month(ds: DataSource, table: str, date_col: str) -> str:
    dialect = (ds.dialect or "sqlite").lower()
    qc = _q(ds, date_col)
    qt = _q(ds, table)
    if dialect in ("mysql", "mariadb"):
        m = f"DATE_FORMAT({qc}, '%Y-%m')"
    elif dialect in ("postgres", "postgresql"):
        m = f"TO_CHAR({qc}::timestamp, 'YYYY-MM')"
    else:
        m = f"STRFTIME('%Y-%m', {qc})"
    return (
        f"SELECT {m} AS month, COUNT(*) AS cnt FROM {qt} "
        f"GROUP BY {m} ORDER BY month LIMIT 24"
    )


def _sql_join_count(ds: DataSource, fk: dict[str, str], cat_col: str | None) -> str | None:
    ft, fc = fk["from_table"], fk["from_column"]
    tt, tc = fk["to_table"], fk["to_column"]
    if cat_col:
        return (
            f"SELECT t.{_q(ds, cat_col)} AS label, COUNT(*) AS cnt "
            f"FROM {_q(ds, ft)} f JOIN {_q(ds, tt)} t "
            f"ON f.{_q(ds, fc)} = t.{_q(ds, tc)} "
            f"GROUP BY t.{_q(ds, cat_col)} ORDER BY cnt DESC LIMIT 10"
        )
    return (
        f"SELECT COUNT(*) AS cnt FROM {_q(ds, ft)} f "
        f"JOIN {_q(ds, tt)} t ON f.{_q(ds, fc)} = t.{_q(ds, tc)}"
    )


def _validate_sql_against_schema(sql: str, schema: dict[str, list[str]], dialect: str) -> bool:
    try:
        validate_sql_safety(sql)
    except Exception:
        return False
    s = sql.strip().upper()
    if not s.startswith("SELECT"):
        return False
    # extract simple identifiers; reject unknown tables
    tables = set(schema.keys())
    # crude: quoted/unquoted table after FROM/JOIN
    tokens = re.findall(
        r"(?:FROM|JOIN)\s+[`\"\[]?([A-Za-z_][A-Za-z0-9_]*)[`\"\]]?",
        sql,
        flags=re.IGNORECASE,
    )
    for t in tokens:
        if t.lower() in ("select", "where", "group", "order", "limit"):
            continue
        if not any(t.lower() == known.lower() for known in tables):
            return False
    return True


def _try_execute(ds: DataSource, sql: str) -> bool:
    try:
        # wrap with limit if missing
        run = sql.rstrip(";")
        if "LIMIT" not in run.upper():
            run = run + " LIMIT 1"
        ds.execute_sql(run)
        return True
    except Exception as e:
        logger.debug(f"bootstrap sql reject: {e} | {sql[:120]}")
        return False


def bootstrap_knowledge_rules(
    datasource_id: str,
    *,
    merge: bool = True,
) -> dict[str, Any]:
    """
    规则引擎生成知识库。
    merge=True：保留用户已有 examples，合并新规则产物（按 question 去重）。
    """
    if datasource_id == BUILTIN_SQLITE_ID:
        # 内置库已有完整 knowledge，不覆盖
        data = load_knowledge(datasource_id)
        return {
            "datasource_id": datasource_id,
            "mode": "skip_builtin",
            "examples_count": len(data.get("question_sql_examples") or []),
            "message": "内置电商知识库已存在，跳过自动覆盖",
        }

    ds = get_datasource(datasource_id)
    schema = _list_schema(ds)
    if not schema:
        return {
            "datasource_id": datasource_id,
            "mode": "empty",
            "examples_count": 0,
            "message": "数据源无表，请先导入数据",
        }

    fks = _infer_fks(schema)
    examples: list[dict[str, Any]] = []
    synonyms: list[dict[str, Any]] = []
    domain: list[dict[str, Any]] = []
    table_schemas: list[dict[str, Any]] = []

    for table, cols in schema.items():
        table_schemas.append(
            {
                "table": table,
                "columns": cols,
                "description": f"表 {table}，共 {len(cols)} 列",
            }
        )
        # synonyms for columns（控制数量，优先分类/数值/日期列）
        prefer_cols = [c for c in cols if _is_cat_col(c) or _is_num_col(c) or _is_date_col(c) or _is_id_col(c)]
        for col in (prefer_cols or cols)[:12]:
            syns = list({col, _humanize(col), col.replace("_", " ")})
            synonyms.append(
                {
                    "synonyms": [s for s in syns if s],
                    "target_column": col,
                    "table": table,
                }
            )

        # COUNT example
        sql = _sql_count(ds, table)
        if _try_execute(ds, sql):
            examples.append(
                {
                    "question": f"{table} 表一共有多少行？",
                    "sql": sql,
                    "tables": [table],
                    "tags": ["auto", "count", "bootstrap"],
                }
            )

        cats = [c for c in cols if _is_cat_col(c)]
        dates = [c for c in cols if _is_date_col(c)]
        nums = [c for c in cols if _is_num_col(c)]

        if cats:
            sql = _sql_group(ds, table, cats[0])
            if _try_execute(ds, sql):
                examples.append(
                    {
                        "question": f"按 {cats[0]} 统计 {table} 数量分布（Top10）",
                        "sql": sql,
                        "tables": [table],
                        "tags": ["auto", "group", "bootstrap"],
                    }
                )
                domain.append(
                    {
                        "term": f"{table}按{cats[0]}分布",
                        "mapping": f"GROUP BY {cats[0]}",
                        "applicable_table": table,
                    }
                )

        if dates:
            sql = _sql_month(ds, table, dates[0])
            if _try_execute(ds, sql):
                examples.append(
                    {
                        "question": f"{table} 按月统计数量趋势",
                        "sql": sql,
                        "tables": [table],
                        "tags": ["auto", "trend", "bootstrap"],
                    }
                )

        if nums and cats:
            # sum by category
            sql = (
                f"SELECT {_q(ds, cats[0])} AS label, SUM({_q(ds, nums[0])}) AS total "
                f"FROM {_q(ds, table)} GROUP BY {_q(ds, cats[0])} "
                f"ORDER BY total DESC LIMIT 10"
            )
            if _try_execute(ds, sql):
                examples.append(
                    {
                        "question": f"{table} 中各 {cats[0]} 的 {nums[0]} 合计排名",
                        "sql": sql,
                        "tables": [table],
                        "tags": ["auto", "sum", "bootstrap"],
                    }
                )

    # JOIN examples from FKs
    for fk in fks[:12]:
        tcols = schema.get(fk["to_table"], [])
        cats = [c for c in tcols if _is_cat_col(c)]
        sql = _sql_join_count(ds, fk, cats[0] if cats else None)
        if sql and _try_execute(ds, sql):
            q = (
                f"关联 {fk['from_table']} 与 {fk['to_table']}，"
                f"按 {cats[0]} 统计数量" if cats else
                f"{fk['from_table']} 与 {fk['to_table']} 关联后的总行数"
            )
            examples.append(
                {
                    "question": q,
                    "sql": sql,
                    "tables": [fk["from_table"], fk["to_table"]],
                    "tags": ["auto", "join", "bootstrap"],
                }
            )
            domain.append(
                {
                    "term": f"{fk['from_table']}.{fk['from_column']}",
                    "mapping": (
                        f"JOIN {fk['to_table']} ON "
                        f"{fk['from_table']}.{fk['from_column']} = "
                        f"{fk['to_table']}.{fk['to_column']}"
                    ),
                    "applicable_table": fk["from_table"],
                }
            )

    # merge with existing
    existing = load_knowledge(datasource_id) if merge else {
        "question_sql_examples": [],
        "synonym_mappings": [],
        "domain_mappings": [],
        "table_schemas": [],
    }

    def _merge_examples(old: list, new: list) -> list:
        seen = {str(e.get("question", "")).strip() for e in old}
        out = list(old)
        for e in new:
            q = str(e.get("question", "")).strip()
            if q and q not in seen:
                out.append(e)
                seen.add(q)
        return out

    def _merge_syn(old: list, new: list) -> list:
        seen = {(e.get("table"), e.get("target_column")) for e in old}
        out = list(old)
        for e in new:
            key = (e.get("table"), e.get("target_column"))
            if key not in seen:
                out.append(e)
                seen.add(key)
        return out

    old_domain = existing.get("domain_mappings") or []
    seen_terms = {str(d.get("term", "")).strip() for d in old_domain}
    merged_domain = list(old_domain)
    for d in domain:
        term = str(d.get("term", "")).strip()
        if term and term not in seen_terms:
            merged_domain.append(d)
            seen_terms.add(term)

    data = {
        "question_sql_examples": _merge_examples(
            existing.get("question_sql_examples") or [], examples
        ),
        "synonym_mappings": _merge_syn(existing.get("synonym_mappings") or [], synonyms),
        "domain_mappings": merged_domain,
        "table_schemas": table_schemas or existing.get("table_schemas") or [],
        "foreign_keys": fks,
        "bootstrap_meta": {
            "mode": "rules",
            "tables": list(schema.keys()),
            "dialect": ds.dialect,
        },
    }

    save_knowledge(data, datasource_id)
    logger.info(
        f"知识库规则 bootstrap 完成 ds={datasource_id} "
        f"examples={len(data['question_sql_examples'])} tables={len(schema)}"
    )
    return {
        "datasource_id": datasource_id,
        "mode": "rules",
        "examples_count": len(data["question_sql_examples"]),
        "synonyms_count": len(data["synonym_mappings"]),
        "domain_mappings_count": len(data["domain_mappings"]),
        "tables": list(schema.keys()),
        "foreign_keys": len(fks),
        "message": (
            f"已为 {len(schema)} 张表生成知识库："
            f"{len(data['question_sql_examples'])} 条示例、"
            f"{len(data['synonym_mappings'])} 条同义词"
        ),
    }


def enhance_knowledge_with_llm(
    datasource_id: str,
    *,
    max_examples: int = 8,
) -> dict[str, Any]:
    """可选：用用户配置模型生成更多 few-shot，校验后合并。"""
    if datasource_id == BUILTIN_SQLITE_ID:
        return {
            "datasource_id": datasource_id,
            "mode": "skip_builtin",
            "added": 0,
            "message": "内置库不使用 AI 覆盖",
        }

    ds = get_datasource(datasource_id)
    schema = _list_schema(ds)
    if not schema:
        return {"datasource_id": datasource_id, "added": 0, "message": "无表可增强"}

    # compact schema text
    lines = [f"方言: {ds.dialect}", f"数据源: {ds.meta.name}"]
    for t, cols in list(schema.items())[:40]:
        lines.append(f"表 {t}: {', '.join(cols[:40])}")
    schema_text = "\n".join(lines)

    from app.models.provider import get_chat_model
    from langchain_core.messages import HumanMessage, SystemMessage

    llm = get_chat_model(temperature=0.2, max_tokens=2048)
    prompt = f"""你是 NL2SQL 知识库生成器。根据真实 Schema 生成 JSON，严禁编造表名/列名。

## Schema
{schema_text}

## 要求
生成最多 {max_examples} 条 few-shot，格式严格为 JSON 数组：
[
  {{"question": "中文问题", "sql": "SELECT ...", "tables": ["t1"], "tags": ["ai"]}}
]
规则：
1. 只输出 JSON 数组，无其它文字
2. SQL 必须是只读 SELECT，符合方言 {ds.dialect}
3. MySQL 用反引号或不用引号，禁止方括号 []
4. SQLite 可用方括号
5. 每条 SQL 建议带 LIMIT
"""
    try:
        resp = llm.invoke(
            [
                SystemMessage(content="只输出合法 JSON 数组。"),
                HumanMessage(content=prompt),
            ]
        )
        text = str(resp.content or "").strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        # extract array
        m = re.search(r"\[.*\]", text, re.DOTALL)
        if not m:
            return {
                "datasource_id": datasource_id,
                "added": 0,
                "message": "模型未返回可解析 JSON",
            }
        items = json.loads(m.group(0))
        if not isinstance(items, list):
            return {"datasource_id": datasource_id, "added": 0, "message": "JSON 非数组"}
    except Exception as e:
        logger.warning(f"LLM knowledge enhance failed: {e}")
        return {
            "datasource_id": datasource_id,
            "added": 0,
            "message": f"AI 增强失败: {e}",
        }

    data = load_knowledge(datasource_id)
    existing_q = {str(e.get("question", "")).strip() for e in data.get("question_sql_examples") or []}
    added = 0
    rejected = 0
    for it in items[: max_examples + 4]:
        if not isinstance(it, dict):
            rejected += 1
            continue
        q = str(it.get("question") or "").strip()
        sql = str(it.get("sql") or "").strip()
        tables = it.get("tables") if isinstance(it.get("tables"), list) else []
        if not q or not sql or q in existing_q:
            rejected += 1
            continue
        # dialect fix brackets for mysql
        dialect = (ds.dialect or "").lower()
        if dialect in ("mysql", "mariadb"):
            sql = re.sub(r"\[([^\]]+)\]", r"`\1`", sql)
        if not _validate_sql_against_schema(sql, schema, dialect):
            rejected += 1
            continue
        if not _try_execute(ds, sql):
            rejected += 1
            continue
        data.setdefault("question_sql_examples", []).append(
            {
                "question": q,
                "sql": sql,
                "tables": tables,
                "tags": list(set((it.get("tags") or []) + ["ai", "enhanced"])),
            }
        )
        existing_q.add(q)
        added += 1
        if added >= max_examples:
            break

    save_knowledge(data, datasource_id)
    return {
        "datasource_id": datasource_id,
        "mode": "llm",
        "added": added,
        "rejected": rejected,
        "examples_count": len(data.get("question_sql_examples") or []),
        "message": f"AI 增强完成：新增 {added} 条，拒绝 {rejected} 条（校验未通过）",
    }


def bootstrap_knowledge(
    datasource_id: str,
    *,
    use_llm: bool = False,
    merge: bool = True,
) -> dict[str, Any]:
    """完整流程：规则必跑 + 可选 LLM。"""
    result = bootstrap_knowledge_rules(datasource_id, merge=merge)
    if use_llm and result.get("mode") not in ("skip_builtin", "empty"):
        llm_result = enhance_knowledge_with_llm(datasource_id)
        result["llm"] = llm_result
        result["examples_count"] = llm_result.get("examples_count", result.get("examples_count"))
        result["message"] = (
            f"{result.get('message', '')}；{llm_result.get('message', '')}"
        ).strip("；")
    return result
