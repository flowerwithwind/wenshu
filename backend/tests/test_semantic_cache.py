"""语义缓存单元测试"""
from __future__ import annotations

import pytest
import numpy as np
from app.services.semantic_cache import SemanticCache, cosine_similarity


class TestCosineSimilarity:
    """余弦相似度计算测试"""

    def test_identical_vectors(self) -> None:
        a = [1.0, 0.0, 0.0]
        b = [1.0, 0.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(1.0)

    def test_orthogonal_vectors(self) -> None:
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert cosine_similarity(a, b) == pytest.approx(0.0)

    def test_similar_vectors(self) -> None:
        a = [1.0, 2.0, 3.0]
        b = [1.1, 2.1, 2.9]
        assert cosine_similarity(a, b) > 0.99

    def test_zero_vector(self) -> None:
        a = [0.0, 0.0, 0.0]
        b = [1.0, 0.0, 0.0]
        assert cosine_similarity(a, b) == 0.0

    def test_empty_vectors(self) -> None:
        a: list[float] = []
        b: list[float] = []
        assert cosine_similarity(a, b) == 0.0


class TestSemanticCache:
    """语义缓存功能测试"""

    @pytest.fixture
    def cache(self) -> SemanticCache:
        """创建语义缓存实例（使用极低阈值确保匹配）"""
        return SemanticCache(threshold=0.01, maxsize=100)

    def test_miss_on_empty_cache(self, cache: SemanticCache) -> None:
        assert cache.get("任何问题") is None

    def test_set_and_get_exact_match(self, cache: SemanticCache) -> None:
        result = {"answer": "42", "sql": "SELECT 42"}
        cache.set("生命的意义", result)
        cached = cache.get("生命的意义")
        assert cached is not None
        # 返回结果应包含原数据
        assert cached["answer"] == "42"
        assert cached["sql"] == "SELECT 42"
        # 语义匹配分数应存在
        assert "_semantic_match_score" in cached

    def test_miss_below_threshold(self) -> None:
        cache = SemanticCache(threshold=0.999, maxsize=100)
        result = {"answer": "数据A"}
        cache.set("2024年销售额", result)
        # 不同问题相似度极低，应未命中
        assert cache.get("你好吗") is None

    def test_lru_eviction(self) -> None:
        cache = SemanticCache(threshold=0.01, maxsize=3)
        items = [
            ("Python编程入门", {"answer": "0"}),
            ("机器学习基础", {"answer": "1"}),
            ("深度学习框架", {"answer": "2"}),
            ("数据库设计原理", {"answer": "3"}),
            ("网络协议分析", {"answer": "4"}),
        ]
        for q, r in items:
            cache.set(q, r)
        assert len(cache._cache) == 3
        # 最早的2条应被淘汰（不在_cache列表中）
        cached_questions = [q for q, e, r in cache._cache]
        assert "Python编程入门" not in cached_questions
        assert "机器学习基础" not in cached_questions
        assert len(cached_questions) == 3

    def test_clear_cache(self, cache: SemanticCache) -> None:
        cache.set("q1", {"answer": "a1"})
        cache.set("q2", {"answer": "a2"})
        assert len(cache._cache) == 2
        cleared = cache.clear()
        assert cleared == 2
        assert len(cache._cache) == 0

    def test_get_stats(self, cache: SemanticCache) -> None:
        stats = cache.get_stats()
        assert stats["type"] == "semantic"
        assert stats["size"] == 0
        assert stats["hit_count"] == 0

        cache.get("q1")  # miss
        stats = cache.get_stats()
        assert stats["miss_count"] == 1

        cache.set("q1", {"answer": "a1"})
        cache.get("q1")  # hit
        stats = cache.get_stats()
        assert stats["hit_count"] == 1

    def test_set_and_get_similar_question(self, cache: SemanticCache) -> None:
        """同一问题不同表述应能命中（低阈值下）"""
        result = {"answer": "电子品类销售额最高"}
        cache.set("销售额最高的品类是什么", result)
        # 非常相似的问题应命中
        cached = cache.get("销售额最高的品类")
        assert cached is not None
        assert cached["answer"] == "电子品类销售额最高"

    def test_not_ready_empty_cache(self) -> None:
        """当 embedding 模型未就绪时，缓存应优雅降级"""
        cache = SemanticCache(threshold=0.5, maxsize=100)
        # 模拟 embedding 模型加载失败
        cache._embedding_model = None
        assert not cache.is_ready
        # get/set 不应抛异常
        assert cache.get("test") is None
        cache.set("test", {"answer": "x"})  # should not error
