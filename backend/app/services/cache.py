"""查询缓存层 - 基于内存的 TTL 缓存，减少重复的 LLM 调用和数据库查询"""
from __future__ import annotations

import hashlib
import time
from cachetools import TTLCache
from app.config import CACHE_MAX_SIZE, CACHE_TTL
from app.logger import get_logger

logger = get_logger(__name__)


_cache: TTLCache = TTLCache(maxsize=CACHE_MAX_SIZE, ttl=CACHE_TTL)
_hit_count: int = 0
_miss_count: int = 0


def _normalize_key(question: str) -> str:
    """对问题做归一化处理，生成缓存 key"""
    return hashlib.md5(question.lower().strip().encode()).hexdigest()[:16]


def get_cache(question: str) -> dict | None:
    """获取缓存结果"""
    global _hit_count, _miss_count
    key: str = _normalize_key(question)
    if key in _cache:
        _hit_count += 1
        cached = _cache[key]
        logger.debug(f"缓存命中: {question[:50]}...")
        # 清理可能过期的引用
        return cached.copy() if isinstance(cached, dict) else cached
    _miss_count += 1
    return None


def set_cache(question: str, result: dict) -> None:
    """设置缓存结果"""
    key: str = _normalize_key(question)
    result["timestamp"] = time.time()
    _cache[key] = result


def clear_cache() -> int:
    """清除所有缓存，返回清除条数"""
    count: int = len(_cache)
    _cache.clear()
    return count


def get_cache_stats() -> dict:
    """获取缓存统计信息"""
    total: int = _hit_count + _miss_count
    hit_rate: float = round(_hit_count / total * 100, 1) if total > 0 else 0.0
    return {
        "cache_size": len(_cache),
        "cache_max_size": CACHE_MAX_SIZE,
        "cache_ttl_seconds": CACHE_TTL,
        "hit_count": _hit_count,
        "miss_count": _miss_count,
        "hit_rate_percent": hit_rate,
    }
