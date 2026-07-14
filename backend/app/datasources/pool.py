"""SQLAlchemy 引擎连接池（MySQL / PostgreSQL）"""
from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus

from app.logger import get_logger

logger = get_logger(__name__)

_engines: dict[str, Any] = {}


def build_sqlalchemy_url(
    db_type: str,
    host: str,
    port: int | None,
    database: str,
    username: str,
    password: str,
) -> str:
    user = quote_plus(username or "")
    pwd = quote_plus(password or "")
    host = host or "127.0.0.1"
    db = database or ""
    t = db_type.lower()
    if t == "mysql":
        p = port or 3306
        return f"mysql+pymysql://{user}:{pwd}@{host}:{p}/{db}?charset=utf8mb4"
    if t in ("postgres", "postgresql"):
        p = port or 5432
        return f"postgresql+psycopg2://{user}:{pwd}@{host}:{p}/{db}"
    raise ValueError(f"不支持的池化类型: {db_type}")


def get_engine(
    ds_id: str,
    db_type: str,
    host: str,
    port: int | None,
    database: str,
    username: str,
    password: str,
    *,
    pool_size: int = 5,
    max_overflow: int = 10,
    pool_recycle: int = 1800,
):
    """获取或创建带连接池的 Engine。"""
    from sqlalchemy import create_engine

    key = ds_id
    if key in _engines:
        return _engines[key]

    url = build_sqlalchemy_url(db_type, host, port, database, username, password)
    engine = create_engine(
        url,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,
        pool_recycle=pool_recycle,
        future=True,
    )
    _engines[key] = engine
    logger.info(f"连接池已创建: id={ds_id} type={db_type} pool_size={pool_size}")
    return engine


def dispose_engine(ds_id: str) -> None:
    eng = _engines.pop(ds_id, None)
    if eng is not None:
        eng.dispose()
        logger.info(f"连接池已释放: id={ds_id}")


def dispose_all() -> None:
    for ds_id in list(_engines.keys()):
        dispose_engine(ds_id)
