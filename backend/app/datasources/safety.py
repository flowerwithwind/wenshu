"""SQL 安全校验 — 全数据源共用"""
from __future__ import annotations

import re
import sqlparse


FORBIDDEN_KEYWORDS: list[str] = [
    "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE",
    "TRUNCATE", "EXEC", "EXECUTE", "ATTACH", "DETACH",
    "PRAGMA", "REINDEX", "VACUUM", "GRANT", "REVOKE",
    "REPLACE", "MERGE", "CALL", "LOAD", "COPY",
]


def validate_sql_safety(sql: str) -> None:
    """只允许 SELECT / WITH ... SELECT；拦截危险关键字。"""
    if not sql or not str(sql).strip():
        raise ValueError("安全拦截: SQL 为空")

    pattern: str = r"\b(?:" + "|".join(FORBIDDEN_KEYWORDS) + r")\b"
    match = re.search(pattern, sql, re.IGNORECASE)
    if match:
        raise ValueError(f"安全拦截: 不允许执行 {match.group().upper()} 操作")

    parsed = sqlparse.parse(sql)
    if not parsed:
        raise ValueError("安全拦截: 无法解析 SQL")

    for stmt in parsed:
        if stmt.get_type() == "UNKNOWN":
            continue
        stmt_type: str = stmt.get_type()
        cleaned: str = sqlparse.format(str(stmt), strip_comments=True).strip().upper()
        if stmt_type not in ("SELECT",) and not cleaned.startswith("WITH"):
            raise ValueError(f"安全拦截: 不允许执行 {stmt_type} 操作")
