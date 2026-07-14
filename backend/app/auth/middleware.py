"""
认证中间件 - FastAPI 依赖注入，提取并验证当前用户
支持 httpOnly Cookie + Authorization Header 双通道
"""
from __future__ import annotations

from fastapi import Request, HTTPException, status

from app.auth.service import decode_token
from app.auth.models import find_user_by_id, UserResponse
from app.logger import get_logger

logger = get_logger(__name__)

# Cookie 名称（与前端约定）
AUTH_COOKIE_NAME = "smartqa_token"


def _extract_token(request: Request) -> str | None:
    """
    从请求中提取 JWT Token
    优先级: Cookie > Authorization Header (Bearer xxx)
    """
    # 1. 优先从 httpOnly Cookie 读取
    token = request.cookies.get(AUTH_COOKIE_NAME)
    if token:
        return token

    # 2. 降级到 Authorization: Bearer <token>
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:].strip()

    return None


def get_current_user(request: Request) -> UserResponse | None:
    """
    尝试获取当前用户（可选认证）
    未登录返回 None，不抛异常
    """
    token = _extract_token(request)
    if not token:
        return None

    payload = decode_token(token)
    if not payload:
        return None

    user_id = int(payload.get("sub", 0))
    user = find_user_by_id(user_id)
    if not user:
        return None

    return UserResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        created_at=user.created_at,
    )


def require_auth(request: Request) -> UserResponse:
    """
    强制认证依赖（必须登录）
    未登录或 Token 无效时抛出 401
    """
    user = get_current_user(request)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录或登录已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
