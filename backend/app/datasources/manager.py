"""数据源配置 CRUD（JSON 持久化 + 密码加密）"""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Any

from app.config import BACKEND_ROOT
from app.datasources.crypto import decrypt_secret, encrypt_secret
from app.datasources.sqlite_ds import BUILTIN_SQLITE_ID
from app.logger import get_logger

logger = get_logger(__name__)

STORE_PATH: Path = BACKEND_ROOT / "data" / "datasources.json"
USER_DB_DIR: Path = BACKEND_ROOT / "data" / "user_dbs"
_lock = threading.Lock()


def _builtin_record() -> dict[str, Any]:
    return {
        "id": BUILTIN_SQLITE_ID,
        "name": "电商演示库 (SQLite)",
        "type": "sqlite",
        "description": "内置电商星型模型（默认，不可删除）",
        "host": "",
        "port": None,
        "database": "knowledge.db",
        "db_path": str((BACKEND_ROOT / "data" / "knowledge.db").resolve()),
        "username": "",
        "password_enc": "",
        "is_default": True,
        "is_builtin": True,
    }


def _load_raw() -> list[dict[str, Any]]:
    if not STORE_PATH.exists():
        data = [_builtin_record()]
        _save_raw(data)
        return data
    try:
        raw = json.loads(STORE_PATH.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raw = []
    except Exception:
        raw = []

    ids = {r.get("id") for r in raw}
    if BUILTIN_SQLITE_ID not in ids:
        raw.insert(0, _builtin_record())
        _save_raw(raw)
    return raw


def _save_raw(records: list[dict[str, Any]]) -> None:
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STORE_PATH.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


def list_datasource_records() -> list[dict[str, Any]]:
    with _lock:
        records = _load_raw()
        defaults = [r for r in records if r.get("is_default")]
        if not defaults:
            for r in records:
                if r.get("id") == BUILTIN_SQLITE_ID:
                    r["is_default"] = True
                    break
            _save_raw(records)
        return [dict(r) for r in records]


def get_record(ds_id: str) -> dict[str, Any] | None:
    for r in list_datasource_records():
        if r.get("id") == ds_id:
            return r
    return None


def resolve_sqlite_path(record: dict[str, Any]) -> str:
    """解析 SQLite 文件绝对路径。"""
    if record.get("id") == BUILTIN_SQLITE_ID or record.get("is_builtin"):
        return str((BACKEND_ROOT / "data" / "knowledge.db").resolve())
    raw = (record.get("db_path") or record.get("database") or "").strip()
    if not raw:
        return str((USER_DB_DIR / f"{record.get('id')}.db").resolve())
    p = Path(raw)
    if not p.is_absolute():
        p = BACKEND_ROOT / "data" / raw
    return str(p.resolve())


def public_record(r: dict[str, Any], *, table_count: int | None = None) -> dict[str, Any]:
    """对外返回：不含密码明文"""
    needs_import = False
    if table_count is not None:
        needs_import = table_count == 0 and not r.get("is_builtin")
    out: dict[str, Any] = {
        "id": r.get("id"),
        "name": r.get("name"),
        "type": r.get("type"),
        "description": r.get("description") or "",
        "host": r.get("host") or "",
        "port": r.get("port"),
        "database": r.get("database") or "",
        "username": r.get("username") or "",
        "has_password": bool(r.get("password_enc")),
        "is_default": bool(r.get("is_default")),
        "is_builtin": bool(r.get("is_builtin")),
        "db_path": r.get("db_path") or "",
        "table_count": table_count,
        "needs_import": needs_import,
        "next_step": (
            "请导入 CSV/Excel 数据表后再进行智能问数"
            if needs_import
            else ""
        ),
    }
    return out


def create_record(payload: dict[str, Any]) -> dict[str, Any]:
    with _lock:
        records = _load_raw()
        ds_type = (payload.get("type") or "mysql").lower()
        if ds_type not in ("sqlite", "mysql", "postgres", "postgresql"):
            raise ValueError("type 必须是 sqlite / mysql / postgres")
        if ds_type == "postgresql":
            ds_type = "postgres"

        ds_id = str(uuid.uuid4())
        password = payload.get("password") or ""
        rec: dict[str, Any] = {
            "id": ds_id,
            "name": (payload.get("name") or f"{ds_type}-{ds_id[:8]}").strip(),
            "type": ds_type,
            "description": (payload.get("description") or "").strip(),
            "host": (payload.get("host") or "").strip(),
            "port": payload.get("port"),
            "database": (payload.get("database") or "").strip(),
            "db_path": "",
            "username": (payload.get("username") or "").strip(),
            "password_enc": encrypt_secret(password) if password else "",
            "is_default": False,
            "is_builtin": False,
        }

        if ds_type == "sqlite":
            # 创建空库文件：创建数据源 ≠ 导入数据
            USER_DB_DIR.mkdir(parents=True, exist_ok=True)
            db_file = USER_DB_DIR / f"{ds_id}.db"
            # 若用户指定了相对文件名
            custom = (payload.get("database") or "").strip()
            if custom and not custom.endswith(".db"):
                custom = f"{custom}.db"
            if custom and "/" not in custom and "\\" not in custom:
                db_file = USER_DB_DIR / custom
            conn = sqlite3.connect(str(db_file))
            conn.close()
            rec["db_path"] = str(db_file.resolve())
            rec["database"] = db_file.name
            if not rec["description"]:
                rec["description"] = "用户 SQLite 库（创建后请导入数据表）"
        else:
            if not rec["database"]:
                raise ValueError("MySQL/PostgreSQL 必须填写 database 名称")
            if not rec["host"]:
                rec["host"] = "127.0.0.1"
            if rec["port"] is None:
                rec["port"] = 5432 if ds_type == "postgres" else 3306

        if payload.get("is_default"):
            for r in records:
                r["is_default"] = False
            rec["is_default"] = True

        records.append(rec)
        _save_raw(records)
        logger.info(f"创建数据源: {rec['name']} ({ds_type})")
        return public_record(rec, table_count=0 if ds_type == "sqlite" else None)


def update_record(ds_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    with _lock:
        records = _load_raw()
        target = None
        for r in records:
            if r.get("id") == ds_id:
                target = r
                break
        if not target:
            raise KeyError("数据源不存在")

        if target.get("is_builtin") and payload.get("type") and payload.get("type") != "sqlite":
            raise ValueError("内置 SQLite 数据源类型不可修改")

        for field in ("name", "description", "host", "database", "username"):
            if field in payload and payload[field] is not None:
                target[field] = str(payload[field]).strip()
        if "port" in payload:
            target["port"] = payload["port"]
        if "password" in payload and payload["password"]:
            pwd = str(payload["password"])
            if "*" not in pwd:
                target["password_enc"] = encrypt_secret(pwd)

        if payload.get("is_default") is True:
            for r in records:
                r["is_default"] = r.get("id") == ds_id

        _save_raw(records)
        return public_record(target)


def delete_record(ds_id: str) -> None:
    with _lock:
        records = _load_raw()
        target = next((r for r in records if r.get("id") == ds_id), None)
        if not target:
            raise KeyError("数据源不存在")
        if target.get("is_builtin") or ds_id == BUILTIN_SQLITE_ID:
            raise ValueError("内置数据源不可删除")
        was_default = bool(target.get("is_default"))
        # 可选删除用户 SQLite 文件
        if target.get("type") == "sqlite" and target.get("db_path"):
            try:
                p = Path(target["db_path"])
                if p.exists() and "user_dbs" in str(p):
                    p.unlink()
            except Exception as e:
                logger.warning(f"删除 SQLite 文件失败: {e}")
        records = [r for r in records if r.get("id") != ds_id]
        if was_default:
            for r in records:
                if r.get("id") == BUILTIN_SQLITE_ID:
                    r["is_default"] = True
                    break
        _save_raw(records)
        logger.info(f"删除数据源: {ds_id}")


def get_password(record: dict[str, Any]) -> str:
    return decrypt_secret(record.get("password_enc") or "")
