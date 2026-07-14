"""数据源密码加解密（Fernet）"""
from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path

from app.config import BACKEND_ROOT
from app.logger import get_logger

logger = get_logger(__name__)

_KEY_FILE: Path = BACKEND_ROOT / "data" / ".ds_secret_key"
_fernet = None


def _get_fernet():
    global _fernet
    if _fernet is not None:
        return _fernet
    try:
        from cryptography.fernet import Fernet
    except ImportError as e:
        raise ImportError("需要 cryptography: pip install cryptography") from e

    _KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    if _KEY_FILE.exists():
        key = _KEY_FILE.read_bytes().strip()
    else:
        # 优先环境变量，否则生成并落盘
        env_key = os.getenv("DATASOURCE_SECRET_KEY", "").strip()
        if env_key:
            # 将任意字符串派生为 32-byte urlsafe key
            digest = hashlib.sha256(env_key.encode("utf-8")).digest()
            key = base64.urlsafe_b64encode(digest)
        else:
            key = Fernet.generate_key()
        _KEY_FILE.write_bytes(key)
        try:
            os.chmod(_KEY_FILE, 0o600)
        except OSError:
            pass
        logger.info("已生成数据源加密密钥文件 data/.ds_secret_key")

    _fernet = Fernet(key)
    return _fernet


def encrypt_secret(plain: str) -> str:
    if not plain:
        return ""
    return _get_fernet().encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt_secret(token: str) -> str:
    if not token:
        return ""
    try:
        return _get_fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except Exception:
        # 兼容历史明文（未加密时）
        return token
