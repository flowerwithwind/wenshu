"""数据源 SQL 审计日志"""
from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from app.config import BACKEND_ROOT
from app.logger import get_logger

logger = get_logger(__name__)

AUDIT_PATH: Path = BACKEND_ROOT / "data" / "sql_audit.jsonl"
_lock = threading.Lock()
MAX_FILE_LINES: int = 5000


def write_audit(
    *,
    datasource_id: str,
    datasource_name: str,
    sql: str,
    ok: bool,
    row_count: int = 0,
    error: str = "",
    duration_ms: float = 0,
    source: str = "pipeline",
    request_id: str = "",
) -> None:
    entry = {
        "id": str(uuid.uuid4()),
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "datasource_id": datasource_id,
        "datasource_name": datasource_name,
        "sql": (sql or "")[:2000],
        "ok": ok,
        "row_count": row_count,
        "error": (error or "")[:500],
        "duration_ms": duration_ms,
        "source": source,
        "request_id": request_id,
    }
    line = json.dumps(entry, ensure_ascii=False)
    try:
        with _lock:
            AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
            with AUDIT_PATH.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
    except Exception as e:
        logger.warning(f"写审计日志失败: {e}")


def list_audit(limit: int = 100, datasource_id: str | None = None) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 500))
    if not AUDIT_PATH.exists():
        return []
    try:
        with _lock:
            lines = AUDIT_PATH.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []

    items: list[dict[str, Any]] = []
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if datasource_id and obj.get("datasource_id") != datasource_id:
            continue
        items.append(obj)
        if len(items) >= limit:
            break
    return items
