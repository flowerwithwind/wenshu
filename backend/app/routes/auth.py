"""
认证路由 - 注册、登录、登出、获取当前用户
JWT 通过 httpOnly Cookie 传递，防止 XSS 窃取
"""
from __future__ import annotations

from fastapi import APIRouter, Response, Depends, HTTPException

from app.auth.models import (
    UserCreate,
    UserLogin,
    UserResponse,
    find_user_by_username,
    insert_user,
    update_last_login,
)
from app.auth.service import hash_password, verify_password, create_token
from app.auth.middleware import require_auth, AUTH_COOKIE_NAME
from app.config import JWT_EXPIRE_HOURS
from app.logger import get_logger

logger = get_logger(__name__)

auth_router = APIRouter(prefix="/api/auth", tags=["认证"])


@auth_router.post("/register", response_model=UserResponse, status_code=201)
async def register(body: UserCreate, response: Response) -> UserResponse:
    """用户注册"""
    # 检查用户名是否已存在
    existing = find_user_by_username(body.username)
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")

    # 创建用户
    pw_hash = hash_password(body.password)
    user = insert_user(body.username, pw_hash, body.display_name or body.username)
    logger.info(f"用户注册: {user.username} (id={user.id})")

    # 注册后自动登录，下发 Cookie
    token = create_token(user.id, user.username)
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        max_age=JWT_EXPIRE_HOURS * 3600,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return UserResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        created_at=user.created_at,
    )


@auth_router.post("/login", response_model=UserResponse)
async def login(body: UserLogin, response: Response) -> UserResponse:
    """用户登录"""
    user = find_user_by_username(body.username)
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    # 更新最后登录时间
    update_last_login(user.id)
    logger.info(f"用户登录: {user.username}")

    # 下发 JWT Cookie
    token = create_token(user.id, user.username)
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        max_age=JWT_EXPIRE_HOURS * 3600,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return UserResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        created_at=user.created_at,
    )


@auth_router.post("/logout")
async def logout(response: Response) -> dict:
    """登出（清除 Cookie）"""
    response.delete_cookie(key=AUTH_COOKIE_NAME, path="/")
    return {"ok": True, "message": "已登出"}


@auth_router.get("/me", response_model=UserResponse)
async def me(user: UserResponse = Depends(require_auth)) -> UserResponse:
    """获取当前登录用户信息"""
    return user
