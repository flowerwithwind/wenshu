"""
统一日志配置 — 基于 loguru 的结构化日志
所有模块通过 from app.logger import get_logger 获取 logger 实例
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path
from loguru import logger


class RequestIDFilter:
    """为 logger 注入 request_id 的上下文过滤器"""
    _request_id: str = "N/A"

    @classmethod
    def set_request_id(cls, rid: str) -> None:
        cls._request_id = rid or "N/A"

    @classmethod
    def get_request_id(cls) -> str:
        return cls._request_id

    @classmethod
    def new_request_id(cls) -> str:
        rid: str = uuid.uuid4().hex[:12]
        cls.set_request_id(rid)
        return rid


def _patch_record(record: dict) -> None:
    """每次写日志时注入当前 request_id（必须是 str，不能 bind lambda）"""
    record["extra"]["request_id"] = RequestIDFilter.get_request_id()


# 移除默认 handler，配置默认 extra
logger.remove()
logger.configure(patcher=_patch_record, extra={"request_id": "N/A"})

# 控制台输出
logger.add(
    sys.stderr,
    format=(
        "<green>{time:HH:mm:ss}</green> | "
        "<level>{level: <7}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    ),
    level="DEBUG",
    colorize=True,
)

# 文件日志
LOG_DIR: Path = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
logger.add(
    LOG_DIR / "smartqa_{time:YYYY-MM-DD}.log",
    format=(
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <7} | "
        "{name}:{function}:{line} | {extra[request_id]:<12} | {message}"
    ),
    level="INFO",
    rotation="100 MB",
    retention="30 days",
    compression="gz",
    enqueue=True,
)

# 错误专用文件
logger.add(
    LOG_DIR / "error_{time:YYYY-MM-DD}.log",
    format=(
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <7} | "
        "{name}:{function}:{line} | {extra[request_id]:<12} | {message}"
    ),
    level="ERROR",
    rotation="100 MB",
    retention="90 days",
    compression="gz",
    enqueue=True,
)


def get_logger(module_name: str | None = None):
    """获取 logger；request_id 由 patcher 动态注入，勿 bind 可调用对象。"""
    if module_name:
        return logger.bind(name=module_name)
    return logger
