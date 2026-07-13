"""
向量存储模块 - 支持 ChromaDB 和 FAISS 两种后端
"""
from __future__ import annotations

import os
from langchain_core.documents import Document
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from app.config import (
    EMBEDDING_MODEL,
    CHROMA_PERSIST_DIR,
)
from app.logging import get_logger

logger = get_logger(__name__)


class VectorStoreManager:
    """向量存储管理器"""

    def __init__(self, persist_dir: str = CHROMA_PERSIST_DIR) -> None:
        self.persist_dir: str = persist_dir
        self.embedding_model: HuggingFaceEmbeddings | None = None
        self.vector_store: Chroma | None = None
        self._init_embeddings()

    def _init_embeddings(self) -> None:
        """初始化嵌入模型"""
        logger.info(f"正在加载嵌入模型: {EMBEDDING_MODEL} ...")
        self.embedding_model = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )

    def create_from_documents(self, documents: list[Document]) -> int:
        """从文档列表创建向量存储"""
        os.makedirs(self.persist_dir, exist_ok=True)

        self.vector_store = Chroma.from_documents(
            documents=documents,
            embedding=self.embedding_model,
            persist_directory=self.persist_dir,
            collection_name="knowledge_base",
        )
        return len(documents)

    def load(self) -> bool:
        """加载已持久化的向量存储"""
        if not os.path.exists(self.persist_dir):
            return False
        try:
            self.vector_store = Chroma(
                persist_directory=self.persist_dir,
                embedding_function=self.embedding_model,
                collection_name="knowledge_base",
            )
            return True
        except Exception as e:
            logger.error(f"加载向量存储失败: {e}")
            return False

    def similarity_search(
        self, query: str, k: int = 4
    ) -> list[Document]:
        """相似度搜索"""
        if not self.vector_store:
            return []
        return self.vector_store.similarity_search(query, k=k)

    def similarity_search_with_score(
        self, query: str, k: int = 4
    ) -> list[tuple[Document, float]]:
        """带分数的相似度搜索"""
        if not self.vector_store:
            return []
        return self.vector_store.similarity_search_with_score(query, k=k)

    def get_collection_stats(self) -> dict[str, int]:
        """获取集合统计信息"""
        if not self.vector_store:
            return {"total": 0}
        try:
            collection = self.vector_store._collection
            count: int = collection.count()
            return {"total": count}
        except Exception:
            return {"total": 0}

    def is_ready(self) -> bool:
        """检查向量存储是否就绪"""
        return self.vector_store is not None
