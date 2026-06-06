"""
检索器模块 - 基于向量相似度的智能检索
"""
from typing import List, Tuple, Optional
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
    ):
        self.vsm = vector_store_manager
        self.k = k
        self.score_threshold = score_threshold

    def retrieve(self, query: str) -> List[Document]:
        """检索相关文档"""
        if not self.vsm.is_ready():
            return []

        results = self.vsm.similarity_search_with_score(query, k=self.k)

        filtered = []
        for doc, score in results:
            if score >= self.score_threshold:
                doc.metadata["score"] = float(score)
                filtered.append(doc)

        return filtered if filtered else [doc for doc, _ in results[:2]]

    def retrieve_with_context(
        self, query: str
    ) -> Tuple[str, List[Document]]:
        """检索并返回格式化的上下文和源文档列表"""
        docs = self.retrieve(query)
        if not docs:
            return "", []

        context_parts = []
        for i, doc in enumerate(docs):
            source = doc.metadata.get("source", "未知")
            context_parts.append(
                f"[来源 {i+1}: {source}]\n{doc.page_content}"
            )

        context = "\n\n---\n\n".join(context_parts)
        return context, docs