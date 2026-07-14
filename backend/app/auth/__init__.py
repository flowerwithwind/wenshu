"""
认证模块 - JWT + httpOnly Cookie 身份验证
提供用户注册、登录、鉴权中间件
"""
from app.auth.service import hash_password, verify_password, create_token, decode_token
from app.auth.middleware import get_current_user, require_auth
from app.auth.models import User, UserCreate, UserLogin, UserResponse, init_auth_db

__all__ = [
    "hash_password",
    "verify_password",
    "create_token",
    "decode_token",
    "get_current_user",
    "require_auth",
    "User",
    "UserCreate",
    "UserLogin",
    "UserResponse",
    "init_auth_db",
]
