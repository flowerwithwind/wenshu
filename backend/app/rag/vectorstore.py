"""
向量存储模块 - ChromaDB 后端
注意：禁止对 Chroma 实例做真值判断（if store），会触发 __len__ -> count()。
重建索引必须先清空集合，否则会在 Windows 文件锁导致 rmtree 失败时反复追加重复块。
"""
from __future__ import annotations

import gc
import os
import shutil
import time
from langchain_core.documents import Document
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from app.config import (
    EMBEDDING_MODEL,
    CHROMA_PERSIST_DIR,
)
from app.logger import get_logger

logger = get_logger(__name__)

COLLECTION_NAME: str = "knowledge_base"


class VectorStoreManager:
    """向量存储管理器"""

    def __init__(self, persist_dir: str = CHROMA_PERSIST_DIR) -> None:
        self.persist_dir: str = persist_dir
        self.embedding_model: HuggingFaceEmbeddings | None = None
        self.vector_store: Chroma | None = None
        self._init_embeddings()

    def _init_embeddings(self) -> None:
        """初始化嵌入模型。

        依赖 torch + sentence-transformers（见 requirements-ml.txt）。
        未安装或加载失败时降级：NL2SQL 主路径仍可用，向量检索不可用。
        """
        try:
            logger.info(f"正在加载嵌入模型: {EMBEDDING_MODEL} ...")
            self.embedding_model = HuggingFaceEmbeddings(
                model_name=EMBEDDING_MODEL,
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )
            logger.info("嵌入模型加载完成")
        except Exception as e:
            self.embedding_model = None
            logger.warning(
                f"嵌入模型加载失败（RAG 向量检索将不可用）: {e}。"
                f"如需本地 BGE Embedding，请安装: pip install -r requirements-ml.txt"
            )

    def _release_store(self) -> None:
        """释放内存中的 Chroma 句柄，便于删除目录/集合"""
        self.vector_store = None
        gc.collect()
        time.sleep(0.1)

    def _wipe_collection_via_client(self) -> bool:
        """通过 PersistentClient 删除所有 collection（比直接 rmtree 更稳）"""
        try:
            import chromadb

            if not os.path.isdir(self.persist_dir):
                return True
            client = chromadb.PersistentClient(path=self.persist_dir)
            for col in list(client.list_collections()):
                try:
                    client.delete_collection(col.name)
                    logger.info(f"已删除 Chroma collection: {col.name}")
                except Exception as e:
                    logger.warning(f"删除 collection {col.name} 失败: {e}")
            return True
        except Exception as e:
            logger.warning(f"Chroma client 清空失败: {e}")
            return False

    def _wipe_persist_dir(self) -> bool:
        """删除持久化目录（带重试）"""
        if not os.path.isdir(self.persist_dir):
            return True
        self._release_store()
        self._wipe_collection_via_client()
        self._release_store()

        for attempt in range(5):
            try:
                shutil.rmtree(self.persist_dir)
                logger.info(f"已清理向量目录: {self.persist_dir}")
                return True
            except OSError as e:
                logger.warning(f"清理向量目录失败 (尝试 {attempt + 1}/5): {e}")
                self._release_store()
                time.sleep(0.4 * (attempt + 1))
        return False

    def _clear_all_ids(self, store: Chroma) -> None:
        """在无法删目录时，删除集合内全部 id，防止追加重复"""
        try:
            batch = 500
            while True:
                data = store._collection.get(include=[], limit=batch)
                ids = data.get("ids") or []
                if not ids:
                    break
                store._collection.delete(ids=ids)
                logger.info(f"已从集合删除 {len(ids)} 条旧向量")
                if len(ids) < batch:
                    break
        except Exception as e:
            logger.warning(f"按 id 清空集合失败: {e}")

    def create_from_documents(self, documents: list[Document]) -> int:
        """
        从文档列表**全量重建**向量存储。
        保证：先清空再写入，避免 Windows 下 rmtree 失败导致块数成倍累计。
        返回集合内实际文档数。
        """
        expected = len(documents)
        if expected == 0:
            return 0
        if self.embedding_model is None:
            logger.error("嵌入模型未就绪，无法重建向量索引（请安装 requirements-ml.txt）")
            return 0

        # 1) 尽量物理清空目录
        wiped = self._wipe_persist_dir()
        os.makedirs(self.persist_dir, exist_ok=True)

        # 2) 若目录未清掉，打开已有 store 并删光 id
        if not wiped:
            logger.warning(
                "向量目录未能完全删除（可能被占用），改为清空 collection 后重写"
            )
            try:
                existing = Chroma(
                    persist_directory=self.persist_dir,
                    embedding_function=self.embedding_model,
                    collection_name=COLLECTION_NAME,
                )
                self._clear_all_ids(existing)
                self.vector_store = existing
            except Exception as e:
                logger.error(f"打开已有集合以清空失败: {e}")
                self.vector_store = None

        # 3) 写入文档
        if self.vector_store is None:
            self.vector_store = Chroma.from_documents(
                documents=documents,
                embedding=self.embedding_model,
                persist_directory=self.persist_dir,
                collection_name=COLLECTION_NAME,
            )
        else:
            # 已清空的集合上追加（此时应为 0 条）
            self.vector_store.add_documents(documents)

        # 4) 校验数量；若仍明显偏大，再强制清一次后重写
        actual = self.get_collection_stats().get("total", 0)
        if actual > expected * 1.1:  # 允许极小误差
            logger.warning(
                f"检测到重复累计: 实际 {actual} 块 > 期望 {expected} 块，强制二次清空重建"
            )
            self._clear_all_ids(self.vector_store)
            after_clear = self.get_collection_stats().get("total", 0)
            if after_clear > 0:
                # 最后手段：换临时目录名不可行，再试 rmtree
                wiped2 = self._wipe_persist_dir()
                os.makedirs(self.persist_dir, exist_ok=True)
                self.vector_store = Chroma.from_documents(
                    documents=documents,
                    embedding=self.embedding_model,
                    persist_directory=self.persist_dir,
                    collection_name=COLLECTION_NAME,
                )
            else:
                self.vector_store.add_documents(documents)
            actual = self.get_collection_stats().get("total", 0)

        logger.info(f"向量重建完成: 写入期望={expected}, 集合实际={actual}")
        if actual != expected:
            logger.warning(
                f"集合数量与写入不一致 (actual={actual}, expected={expected})，"
                "请停止所有后端进程后执行 python scripts/rebuild_index.py"
            )
        return actual

    def _probe_store(self, store: Chroma) -> bool:
        """探测索引是否可读"""
        try:
            store._collection.count()
            return True
        except Exception as e:
            logger.warning(f"向量索引不可用（可能损坏）: {e}")
            return False

    def load(self) -> bool:
        """加载已持久化的向量存储；损坏时返回 False。"""
        if self.embedding_model is None:
            logger.warning("嵌入模型未就绪，跳过向量库加载")
            return False
        if not os.path.exists(self.persist_dir):
            return False
        try:
            store = Chroma(
                persist_directory=self.persist_dir,
                embedding_function=self.embedding_model,
                collection_name=COLLECTION_NAME,
            )
            if not self._probe_store(store):
                self.vector_store = None
                logger.warning(
                    "Chroma 索引探测失败，已跳过加载。"
                    "请执行: POST /api/rebuild-index 或 python scripts/rebuild_index.py"
                )
                return False
            self.vector_store = store
            return True
        except Exception as e:
            logger.error(f"加载向量存储失败: {e}")
            self.vector_store = None
            return False

    def reset_corrupt_index(self) -> None:
        """删除持久化目录（重建前调用）"""
        self._wipe_persist_dir()

    def similarity_search(self, query: str, k: int = 4) -> list[Document]:
        if self.vector_store is None:
            return []
        try:
            return self.vector_store.similarity_search(query, k=k)
        except Exception as e:
            logger.error(f"相似度搜索失败: {e}")
            return []

    def similarity_search_with_score(
        self, query: str, k: int = 4
    ) -> list[tuple[Document, float]]:
        if self.vector_store is None:
            return []
        try:
            return self.vector_store.similarity_search_with_score(query, k=k)
        except Exception as e:
            logger.error(f"带分搜索失败: {e}")
            return []

    def get_collection_stats(self) -> dict[str, int]:
        if self.vector_store is None:
            return {"total": 0}
        try:
            count: int = self.vector_store._collection.count()
            return {"total": count}
        except Exception as e:
            logger.warning(f"读取向量集合统计失败: {e}")
            return {"total": 0}

    def is_ready(self) -> bool:
        return self.vector_store is not None
