"""
语义缓存 - 基于 embedding 相似度的查询缓存

与精确缓存（app.services.cache）不同，语义缓存可以匹配语义相似
但表述不同的问题，减少重复的 LLM 调用。

原理:
1. 缓存时：计算问题的 embedding 并存入内存
2. 查询时：计算新问题的 embedding，与所有缓存项计算余弦相似度
3. 相似度超过阈值(默认0.92)时，直接返回缓存结果
"""
from __future__ import annotations

import time
import numpy as np
from typing import Any
from langchain_community.embeddings import HuggingFaceEmbeddings
from app.config import EMBEDDING_MODEL, CACHE_MAX_SIZE
from app.logging import get_logger

logger = get_logger(__name__)

# 默认相似度阈值
DEFAULT_SIMILARITY_THRESHOLD: float = 0.92

# 缓存条目: (question, embedding, result_dict)
_CacheEntry = tuple[str, list[float], dict[str, Any]]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """计算两个向量的余弦相似度"""
    a_np = np.array(a, dtype=np.float32)
    b_np = np.array(b, dtype=np.float32)
    if np.linalg.norm(a_np) == 0 or np.linalg.norm(b_np) == 0:
        return 0.0
    return float(np.dot(a_np, b_np) / (np.linalg.norm(a_np) * np.linalg.norm(b_np)))


class SemanticCache:
    """基于 embedding 相似度的语义缓存"""

    def __init__(
        self,
        threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        maxsize: int = CACHE_MAX_SIZE,
    ) -> None:
        self.threshold: float = threshold
        self.maxsize: int = maxsize
        self._cache: list[_CacheEntry] = []
        self._hit_count: int = 0
        self._miss_count: int = 0
        self._embedding_model: HuggingFaceEmbeddings | None = None
        self._init_embeddings()

    def _init_embeddings(self) -> None:
        """初始化 embedding 模型"""
        try:
            self._embedding_model = HuggingFaceEmbeddings(
                model_name=EMBEDDING_MODEL,
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )
            logger.info(f"语义缓存嵌入模型已加载: {EMBEDDING_MODEL}")
        except Exception as e:
            logger.warning(f"语义缓存嵌入模型加载失败，将回退到精确匹配: {e}")

    @property
    def is_ready(self) -> bool:
        """检查 embedding 模型是否就绪"""
        return self._embedding_model is not None

    def _embed(self, text: str) -> list[float]:
        """计算文本的 embedding 向量"""
        if not self._embedding_model:
            return []
        return self._embedding_model.embed_query(text)

    def get(self, question: str) -> dict[str, Any] | None:
        """查找语义相似的缓存结果

        遍历所有缓存项，返回相似度最高的结果（如果超过阈值）。
        """
        if not self.is_ready or not self._cache:
            self._miss_count += 1
            return None

        emb = self._embed(question)
        if not emb:
            self._miss_count += 1
            return None

        best_score: float = 0.0
        best_result: dict[str, Any] | None = None

        for cached_q, cached_emb, cached_result in self._cache:
            score = cosine_similarity(emb, cached_emb)
            if score > best_score:
                best_score = score
                best_result = cached_result

        if best_score >= self.threshold and best_result is not None:
            self._hit_count += 1
            logger.debug(f"语义缓存命中: '{question[:30]}...' ~ 相似度={best_score:.4f}")
            return {**best_result, "_semantic_match_score": best_score}

        self._miss_count += 1
        logger.debug(f"语义缓存未命中: '{question[:30]}...' 最高相似度={best_score:.4f}")
        return None

    def set(self, question: str, result: dict[str, Any]) -> None:
        """存入语义缓存"""
        if not self.is_ready:
            return

        emb = self._embed(question)
        if not emb:
            return

        # LRU 淘汰：超出容量时移除最早条目
        if len(self._cache) >= self.maxsize:
            self._cache.pop(0)

        self._cache.append((question, emb, result))
        logger.debug(f"语义缓存已存入: '{question[:30]}...' (共{len(self._cache)}项)")

    def clear(self) -> int:
        """清除所有语义缓存"""
        count = len(self._cache)
        self._cache.clear()
        return count

    def get_stats(self) -> dict[str, Any]:
        """获取缓存统计"""
        total = self._hit_count + self._miss_count
        hit_rate = round(self._hit_count / total * 100, 1) if total > 0 else 0.0
        return {
            "type": "semantic",
            "size": len(self._cache),
            "maxsize": self.maxsize,
            "threshold": self.threshold,
            "hit_count": self._hit_count,
            "miss_count": self._miss_count,
            "hit_rate_percent": hit_rate,
        }


# 全局单例
_semantic_cache: SemanticCache | None = None


def get_semantic_cache() -> SemanticCache:
    """获取语义缓存单例"""
    global _semantic_cache
    if _semantic_cache is None:
        _semantic_cache = SemanticCache()
    return _semantic_cache
