from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

# backend/ 根目录（与 cwd 无关，避免从 app/ 启动时找不到 data/）
BACKEND_ROOT: Path = Path(__file__).resolve().parent.parent
_ENV_FILE = BACKEND_ROOT / ".env"
load_dotenv(_ENV_FILE if _ENV_FILE.exists() else None)


def _path_from_env(key: str, default_relative: str) -> str:
    """读取路径配置；相对路径一律锚定到 backend 根目录。"""
    raw: str = os.getenv(key, default_relative)
    p = Path(raw)
    if not p.is_absolute():
        p = BACKEND_ROOT / p
    return str(p.resolve())


# LLM 供应商选择: deepseek / openai / anthropic
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "deepseek").lower()

# DeepSeek API 配置
DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# OpenAI API 配置
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")

# Anthropic API 配置
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

# Embedding 模型配置
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-zh-v1.5")

# 向量数据库配置（绝对路径）
VECTOR_DB_PATH: str = _path_from_env("VECTOR_DB_PATH", "data/vector_db")
CHROMA_PERSIST_DIR: str = _path_from_env("CHROMA_PERSIST_DIR", "data/chroma_db")

# 文档处理配置
CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "500"))
CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "50"))
MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))

# 检索配置
RETRIEVER_K: int = int(os.getenv("RETRIEVER_K", "4"))
RETRIEVER_SCORE_THRESHOLD: float = float(os.getenv("RETRIEVER_SCORE_THRESHOLD", "0.0"))

# 服务配置
HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "8000"))
CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "*").split(",")

# 数据集配置（绝对路径）
DATASET_DIR: str = _path_from_env("DATASET_DIR", "data/datasets")

# 缓存配置
CACHE_MAX_SIZE: int = int(os.getenv("CACHE_MAX_SIZE", "500"))
CACHE_TTL: int = int(os.getenv("CACHE_TTL", "1800"))

# 限流配置
RATE_LIMIT_MAX_REQUESTS: int = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "60"))
RATE_LIMIT_WINDOW_SECONDS: int = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))

# OpenTelemetry 配置
OTEL_SERVICE_NAME: str = os.getenv("OTEL_SERVICE_NAME", "smartqa")
OTEL_EXPORTER_OTLP_ENDPOINT: str | None = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT") or None

# JWT 认证配置
JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "smartqa-dev-secret-change-me-in-prod")
JWT_ALGORITHM: str = "HS256"
JWT_EXPIRE_HOURS: int = int(os.getenv("JWT_EXPIRE_HOURS", "24"))
# auth.db 路径（独立于业务数据库，职责单一）
AUTH_DB_PATH: str = _path_from_env("AUTH_DB_PATH", "data/auth.db")
