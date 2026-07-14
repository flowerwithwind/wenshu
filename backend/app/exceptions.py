"""统一错误处理体系 - 错误码枚举、错误消息映射、异常分类"""
from __future__ import annotations

from enum import Enum


class ErrorCode(str, Enum):
    SQL_GENERATION_FAILED = "SQL_GENERATION_FAILED"
    SQL_EXECUTION_ERROR = "SQL_EXECUTION_ERROR"
    SQL_EMPTY_RESULT = "SQL_EMPTY_RESULT"
    SQL_TIMEOUT = "SQL_TIMEOUT"
    SAFETY_VIOLATION = "SAFETY_VIOLATION"
    LLM_SERVICE_ERROR = "LLM_SERVICE_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    INVALID_REQUEST = "INVALID_REQUEST"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    UNSUPPORTED_FILE_TYPE = "UNSUPPORTED_FILE_TYPE"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    VECTOR_STORE_ERROR = "VECTOR_STORE_ERROR"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"


ERROR_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.SQL_GENERATION_FAILED: "SQL 生成失败，请检查问题描述",
    ErrorCode.SQL_EXECUTION_ERROR: "SQL 执行出错",
    ErrorCode.SQL_EMPTY_RESULT: "未找到匹配数据",
    ErrorCode.SQL_TIMEOUT: "SQL 查询超时",
    ErrorCode.SAFETY_VIOLATION: "安全拦截: 不允许执行危险操作",
    ErrorCode.LLM_SERVICE_ERROR: "LLM 模型服务异常，请稍后重试",
    ErrorCode.DATABASE_ERROR: "数据库错误",
    ErrorCode.INVALID_REQUEST: "请求参数无效",
    ErrorCode.FILE_TOO_LARGE: "上传文件过大",
    ErrorCode.UNSUPPORTED_FILE_TYPE: "不支持的文件类型",
    ErrorCode.RATE_LIMIT_EXCEEDED: "请求过于频繁，请稍后重试",
    ErrorCode.VECTOR_STORE_ERROR: "向量存储错误",
    ErrorCode.UNAUTHORIZED: "未登录或登录已过期",
    ErrorCode.FORBIDDEN: "权限不足",
}

HTTP_STATUS_MAP: dict[ErrorCode, int] = {
    ErrorCode.INVALID_REQUEST: 400,
    ErrorCode.UNAUTHORIZED: 401,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.RATE_LIMIT_EXCEEDED: 429,
    ErrorCode.FILE_TOO_LARGE: 413,
    ErrorCode.UNSUPPORTED_FILE_TYPE: 415,
    ErrorCode.SAFETY_VIOLATION: 403,
    ErrorCode.SQL_TIMEOUT: 504,
    ErrorCode.SQL_EMPTY_RESULT: 200,
}

# 异常类型 -> 错误码映射
EXCEPTION_ERROR_CODE_MAP: dict[str, ErrorCode] = {
    "ValueError": ErrorCode.SAFETY_VIOLATION,
    "sqlite3.OperationalError": ErrorCode.SQL_EXECUTION_ERROR,
    "sqlite3.DatabaseError": ErrorCode.DATABASE_ERROR,
    "sqlite3.TimeoutError": ErrorCode.SQL_TIMEOUT,
    "TimeoutError": ErrorCode.SQL_TIMEOUT,
    "openai.APIError": ErrorCode.LLM_SERVICE_ERROR,
    "openai.APITimeoutError": ErrorCode.LLM_SERVICE_ERROR,
    "openai.RateLimitError": ErrorCode.RATE_LIMIT_EXCEEDED,
}


def classify_exception(e: Exception) -> ErrorCode:
    """根据异常类型映射到对应的错误码"""
    exc_type: str = type(e).__qualname__
    exc_module: str = type(e).__module__
    full_name: str = f"{exc_module}.{exc_type}" if exc_module != "builtins" else exc_type

    # 检查异常消息中是否包含安全相关关键词
    msg: str = str(e).upper()
    if "安全拦截" in msg:
        return ErrorCode.SAFETY_VIOLATION

    # 按模块名+类型名匹配
    for key, code in EXCEPTION_ERROR_CODE_MAP.items():
        if full_name == key or exc_type == key:
            return code

    # 模糊匹配
    if "timeout" in exc_type.lower():
        return ErrorCode.SQL_TIMEOUT
    if "sqlite" in exc_type.lower():
        return ErrorCode.DATABASE_ERROR
    if "openai" in exc_type.lower():
        return ErrorCode.LLM_SERVICE_ERROR

    return ErrorCode.SQL_EXECUTION_ERROR
