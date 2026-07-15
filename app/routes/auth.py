"""
认证路由 - 注册、登录、登出、获取当前用户
JWT 通过 httpOnly Cookie 传递，防止 XSS 窃取
"""
from __future__ import annotations

from fastapi import APIRouter, Response, Depends, HTTPException

from app.auth.models import (
    UserCreate, UserLogin, UserResponse, create_user, find_user_by_username,
    verify_password, create_token, get_user_from_token, AUTH_COOKIE_NAME,
)
from app.auth.middleware import require_auth
from app.logger import get_logger

logger = get_logger(__name__)

auth_router = APIRouter(prefix="/api/auth", tags=["认证"])


@auth_router.post("/register", response_model=UserResponse, status_code=201)
async def register(body: UserCreate, response: Response) -> UserResponse:
    """用户注册"""
    if find_user_by_username(body.username):
        raise HTTPException(status_code=409, detail="用户名已存在")
    user = create_user(body.username, body.password)
    token = create_token(user.id)
    response.set_cookie(
        key=AUTH_COOKIE_NAME, value=token, httponly=True, max_age=86400,
        samesite="lax", path="/",
    )
    logger.info(f"新用户注册: {user.username}")
    return UserResponse(id=user.id, username=user.username, created_at=user.created_at)


@auth_router.post("/login", response_model=UserResponse)
async def login(body: UserLogin, response: Response) -> UserResponse:
    """用户登录"""
    user = find_user_by_username(body.username)
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_token(user.id)
    response.set_cookie(
        key=AUTH_COOKIE_NAME, value=token, httponly=True, max_age=86400,
        samesite="lax", path="/",
    )
    logger.info(f"用户登录: {user.username}")
    return UserResponse(id=user.id, username=user.username, created_at=user.created_at)


@auth_router.post("/logout")
async def logout(response: Response) -> dict:
    """登出（清除 Cookie）"""
    response.delete_cookie(key=AUTH_COOKIE_NAME, path="/")
    return {"ok": True, "message": "已登出"}


@auth_router.get("/me", response_model=UserResponse)
async def me(user: UserResponse = Depends(require_auth)) -> UserResponse:
    """获取当前登录用户信息"""
    return user
