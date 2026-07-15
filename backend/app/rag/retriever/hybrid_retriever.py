"""
混合检索融合器 - 语义检索 + BM25 关键词检索的加权融合

核心策略:
1. 语义检索 (ChromaDB cosine similarity): 擅长语义泛化
2. BM25 关键词检索: 擅长精确术语匹配
3. 分数归一化 → 加权融合 → 去重排序

融合公式:
    final_score = alpha * norm(semantic_score) + (1-alpha) * norm(bm25_score)

用法:
    hybrid = HybridRetriever(semantic_retriever, bm25_retriever, alpha=0.7)
    docs = hybrid.retrieve("上个月销量最高的产品", k=4)
"""
from __future__ import annotations

import time
from typing import Any

from langchain_core.documents import Document
from app.logger import get_logger

logger = get_logger(__name__)


class HybridRetriever:
    """混合检索器：语义 + BM25 加权融合"""

    def __init__(
        self,
        semantic_retriever: Any,
        bm25_retriever: Any,
        alpha: float = 0.7,
    ) -> None:
        """
        Args:
            semantic_retriever: 语义检索器实例（需有 retrieve() 方法返回 [(Document, score)]）
            bm25_retriever: BM25 检索器实例
            alpha: 语义权重 (0~1)，1 表示纯语义，0 表示纯 BM25
        """
        self.semantic = semantic_retriever
        self.bm25 = bm25_retriever
        self.alpha = alpha
        self._fusion_cache: dict[str, list[Document]] = {}

    @property
    def is_ready(self) -> bool:
        """至少一路可用"""
        return bool(self.semantic) or bool(self.bm25)

    def retrieve(
        self, query: str, k: int = 4, force_refresh: bool = False
    ) -> list[Document]:
        """
        混合检索：融合语义 + BM25 结果

        Args:
            query: 查询文本
            k: 返回数量
            force_refresh: 强制重新检索（跳过缓存）

        Returns:
            融合排序后的 Document 列表
        """
        cache_key = f"{query}::k={k}"
        if not force_refresh and cache_key in self._fusion_cache:
            return self._fusion_cache[cache_key]

        start = time.time()

        # Step 1: 分别检索
        semantic_results = self._safe_retrieve(self.semantic, query, k * 2)
        bm25_results = self._safe_retrieve(self.bm25, query, k * 2)

        # Step 2: 分数归一化
        semantic_norm = self._normalize_scores(semantic_results)
        bm25_norm = self._normalize_scores(bm25_results)

        # Step 3: 加权融合（合并所有文档，按融合分数排序）
        fused: dict[str, tuple[Document, float]] = {}

        for doc, norm_score in semantic_norm:
            doc_id = doc.metadata.get("source", "") + doc.page_content[:50]
            fused_score = self.alpha * norm_score
            if doc_id in fused:
                fused[doc_id] = (doc, fused[doc_id][1] + fused_score)
            else:
                doc.metadata["hybrid_score"] = round(fused_score, 4)
                doc.metadata["semantic_score"] = round(norm_score, 4)
                doc.metadata["bm25_score"] = 0
                fused[doc_id] = (doc, fused_score)

        for doc, norm_score in bm25_norm:
            doc_id = doc.metadata.get("source", "") + doc.page_content[:50]
            fused_score = (1 - self.alpha) * norm_score
            if doc_id in fused:
                old_total = fused[doc_id][1]
                old_doc = fused[doc_id][0]
                old_doc.metadata["hybrid_score"] = round(old_total + fused_score, 4)
                old_doc.metadata["bm25_score"] = round(norm_score, 4)
                fused[doc_id] = (old_doc, old_total + fused_score)
            else:
                doc.metadata["hybrid_score"] = round(fused_score, 4)
                doc.metadata["semantic_score"] = 0
                doc.metadata["bm25_score"] = round(norm_score, 4)
                fused[doc_id] = (doc, fused_score)

        # Step 4: 按融合分数降序排列，取 Top-K
        sorted_docs = sorted(fused.values(), key=lambda x: x[1], reverse=True)[:k]
        result_docs = [doc for doc, _ in sorted_docs]

        elapsed = (time.time() - start) * 1000
        logger.debug(
            f"混合检索: semantic={len(semantic_results)}, "
            f"bm25={len(bm25_results)}, fused={len(result_docs)}, "
            f"alpha={self.alpha}, {elapsed:.0f}ms"
        )

        self._fusion_cache[cache_key] = result_docs
        return result_docs

    def retrieve_with_context(
        self, query: str, k: int = 4
    ) -> tuple[str, list[Document]]:
        """检索并返回格式化上下文"""
        docs = self.retrieve(query, k=k)
        if not docs:
            return "", []

        context_parts = []
        for i, doc in enumerate(docs):
            source = doc.metadata.get("source", "未知")
            hybrid = doc.metadata.get("hybrid_score", 0)
            context_parts.append(
                f"[来源 {i+1}: {source} (hybrid_score={hybrid})]\n{doc.page_content}"
            )

        context = "\n\n---\n\n".join(context_parts)
        return context, docs

    def set_alpha(self, alpha: float) -> None:
        """运行时调整语义/关键词权重"""
        self.alpha = max(0.0, min(1.0, alpha))
        self._fusion_cache.clear()
        logger.info(f"混合检索权重调整: alpha={self.alpha}")

    # -------- 内部辅助方法 --------

    def _safe_retrieve(
        self, retriever: Any, query: str, k: int
    ) -> list[tuple[Document, float]]:
        """安全检索，防止空/异常"""
        if retriever is None:
            return []
        try:
            if hasattr(retriever, "retrieve"):
                # BM25 / SmartRetriever 接口
                results = retriever.retrieve(query, k=k)
                # 兼容返回 list[Document] 和 list[tuple[Document, float]]
                if results and isinstance(results[0], tuple):
                    return results
                elif results and isinstance(results[0], Document):
                    return [(doc, doc.metadata.get("score", 0)) for doc in results]
            return []
        except Exception as e:
            logger.warning(f"混合检索子模块异常 ({type(retriever).__name__}): {e}")
            return []

    @staticmethod
    def _normalize_scores(
        results: list[tuple[Document, float]]
    ) -> list[tuple[Document, float]]:
        """Min-Max 归一化到 [0, 1]"""
        if not results:
            return []
        scores = [s for _, s in results]
        min_s, max_s = min(scores), max(scores)
        if max_s == min_s:
            return [(doc, 1.0) for doc, _ in results]
        return [(doc, (s - min_s) / (max_s - min_s)) for doc, s in results]
