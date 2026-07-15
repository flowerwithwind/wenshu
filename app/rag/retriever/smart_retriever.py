"""
检索器模块 - 基于向量相似度的智能检索
"""
from __future__ import annotations

from langchain_core.documents import Document
from app.config import RETRIEVER_K, RETRIEVER_SCORE_THRESHOLD
from app.rag.vectorstore import VectorStoreManager


class SmartRetriever:
    """智能检索器，支持多策略检索"""

    def __init__(
        self,
        vector_store_manager: VectorStoreManager,
        k: int = RETRIEVER_K,
        score_threshold: float = RETRIEVER_SCORE_THRESHOLD,
    ) -> None:
        self.vsm: VectorStoreManager = vector_store_manager
        self.k: int = k
        self.score_threshold: float = score_threshold

    def retrieve(self, query: str, k: int | None = None) -> list[Document]:
        if not self.vsm.is_ready():
            return []
        k = k or self.k
        results = self.vsm.similarity_search_with_score(query, k=k)
        scored = []
        for doc, distance in results:
            similarity = max(0.0, min(1.0, 1.0 - distance / 2.0))
            doc.metadata["score"] = round(similarity, 4)
            scored.append((doc, similarity))
        filtered = [(doc, sim) for doc, sim in scored if sim >= self.score_threshold]
        if filtered:
            filtered.sort(key=lambda x: x[1], reverse=True)
            return [doc for doc, _ in filtered]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [doc for doc, _ in scored[:2]]

    def retrieve_with_context(self, query: str) -> tuple[str, list[Document]]:
        docs = self.retrieve(query)
        if not docs:
            return "", []
        parts = []
        for i, doc in enumerate(docs):
            src = doc.metadata.get("source", "未知")
            parts.append(f"[来源 {i+1}: {src}]\n{doc.page_content}")
        return "\n\n---\n\n".join(parts), docs
