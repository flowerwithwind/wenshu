"""
认证服务层 - 密码哈希、JWT 生成/解析
bcrypt 哈希 + PyJWT 签名，安全性优先
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import JWT_SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRE_HOURS
from app.logger import get_logger

logger = get_logger(__name__)


def hash_password(plain: str) -> str:
    """bcrypt 哈希密码（自动加盐，12 轮）"""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """校验密码是否匹配"""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_token(user_id: int, username: str) -> str:
    """
    生成 JWT Token
    payload 仅包含必要信息：user_id、username、过期时间
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "username": username,
        "iat": now,
        "exp": now + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict | None:
    """
    解析 JWT Token，返回 payload 字典
    过期或签名无效返回 None
    """
    try:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        logger.debug("JWT 已过期")
        return None
    except jwt.InvalidTokenError as e:
        logger.debug(f"JWT 无效: {e}")
        return None
