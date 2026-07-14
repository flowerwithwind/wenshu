"""
用户数据模型 + auth.db 建表
独立 auth.db 避免与业务数据库耦合，便于后续迁移到 PostgreSQL
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pydantic import BaseModel, Field
from app.config import AUTH_DB_PATH
from app.logger import get_logger

logger = get_logger(__name__)


# ── Pydantic 请求/响应模型 ──────────────────────────────────────────────

class UserCreate(BaseModel):
    """注册请求体"""
    username: str = Field(..., min_length=3, max_length=20, description="登录名，3-20字符")
    password: str = Field(..., min_length=6, max_length=64, description="密码，6位以上")
    display_name: str = Field(default="", max_length=30, description="显示昵称")


class UserLogin(BaseModel):
    """登录请求体"""
    username: str = Field(..., min_length=1, description="用户名")
    password: str = Field(..., min_length=1, description="密码")


class User(BaseModel):
    """内部用户记录（含密码哈希，不对外暴露）"""
    id: int
    username: str
    password_hash: str
    display_name: str
    created_at: str
    last_login: str | None = None


class UserResponse(BaseModel):
    """对外返回的用户信息（脱敏）"""
    id: int
    username: str
    display_name: str
    created_at: str


# ── 数据库操作 ──────────────────────────────────────────────────────────

def _get_conn() -> sqlite3.Connection:
    """获取 auth.db 连接（每次调用都新建，短生命周期操作足够）"""
    conn = sqlite3.connect(AUTH_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_auth_db() -> None:
    """建表（幂等），应用启动时调用"""
    conn = _get_conn()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                username     TEXT    NOT NULL UNIQUE,
                password_hash TEXT   NOT NULL,
                display_name TEXT    DEFAULT '',
                created_at   TEXT    NOT NULL,
                last_login   TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)
        """)
        conn.commit()
        logger.info(f"auth.db 就绪: {AUTH_DB_PATH}")
    finally:
        conn.close()


def find_user_by_username(username: str) -> User | None:
    """按用户名查询"""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        return User(**dict(row)) if row else None
    finally:
        conn.close()


def find_user_by_id(user_id: int) -> User | None:
    """按 ID 查询"""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        return User(**dict(row)) if row else None
    finally:
        conn.close()


def insert_user(username: str, password_hash: str, display_name: str) -> User:
    """插入新用户，返回完整 User 对象"""
    now = datetime.now().isoformat(timespec="seconds")
    conn = _get_conn()
    try:
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash, display_name, created_at) VALUES (?, ?, ?, ?)",
            (username, password_hash, display_name, now),
        )
        conn.commit()
        return User(
            id=cursor.lastrowid,
            username=username,
            password_hash=password_hash,
            display_name=display_name,
            created_at=now,
        )
    finally:
        conn.close()


def update_last_login(user_id: int) -> None:
    """更新最后登录时间"""
    now = datetime.now().isoformat(timespec="seconds")
    conn = _get_conn()
    try:
        conn.execute("UPDATE users SET last_login = ? WHERE id = ?", (now, user_id))
        conn.commit()
    finally:
        conn.close()
