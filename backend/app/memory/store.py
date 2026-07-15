"""
长期记忆存储模块

基于 ChromaDB 存储对话摘要向量，支持按时间衰减权重检索。

每条记忆作为 Document 存入 ChromaDB，元数据包含：
- conversation_id: 对话 ID
- timestamp: 创建时间
- turn_count: 对话轮次
- user_intent: 用户意图
- key_entities: 关键实体列表
"""
from __future__ import annotations

import json
import time
from typing import Any
from pathlib import Path

from langchain_core.documents import Document
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from app.config import EMBEDDING_MODEL
from app.logger import get_logger

logger = get_logger(__name__)

MEMORY_PERSIST_DIR = str(
    Path(__file__).resolve().parent.parent.parent / "data" / "memory_store"
)
COLLECTION_NAME = "agent_memories"

# 时间衰减参数
TIME_DECAY_FRESH_HOURS = 1      # 近1小时权重 1.0
TIME_DECAY_NORMAL_HOURS = 24    # 1-24小时权重 0.7
TIME_DECAY_OLD_WEIGHT = 0.3     # 超过24小时权重


class MemoryStore:
    """长期记忆存储"""

    def __init__(self) -> None:
        self.persist_dir: str = MEMORY_PERSIST_DIR
        self._embeddings: HuggingFaceEmbeddings | None = None
        self._store: Chroma | None = None
        self._init_embeddings()
        self._init_store()

    def _init_embeddings(self) -> None:
        try:
            self._embeddings = HuggingFaceEmbeddings(
                model_name=EMBEDDING_MODEL,
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )
        except Exception as e:
            logger.warning(f"记忆存储 Embedding 加载失败: {e}")

    def _init_store(self) -> None:
        if self._embeddings is None:
            return
        try:
            Path(self.persist_dir).mkdir(parents=True, exist_ok=True)
            self._store = Chroma(
                persist_directory=self.persist_dir,
                embedding_function=self._embeddings,
                collection_name=COLLECTION_NAME,
            )
            # 探测是否可用
            self._store._collection.count()
            logger.info("记忆存储 ChromaDB 就绪")
        except Exception:
            # 首次初始化：使用空集合
            try:
                self._store = Chroma.from_documents(
                    documents=[Document(page_content="init", metadata={"init": True})],
                    embedding=self._embeddings,
                    persist_directory=self.persist_dir,
                    collection_name=COLLECTION_NAME,
                )
                # 删除初始化占位
                self._store._collection.delete(ids=self._store._collection.get()["ids"])
                logger.info("记忆存储 ChromaDB 初始化完成")
            except Exception as e:
                logger.warning(f"记忆存储初始化失败: {e}")
                self._store = None

    def is_ready(self) -> bool:
        return self._store is not None

    def save_memory(self, summary: dict[str, Any]) -> str | None:
        """
        保存一条记忆

        Returns:
            记忆 ID
        """
        if not self.is_ready() or self._store is None:
            return None

        content = json.dumps(summary, ensure_ascii=False)
        doc = Document(
            page_content=content,
            metadata={
                "conversation_id": summary.get("conversation_id", ""),
                "timestamp": time.time(),
                "turn_count": summary.get("turn_count", 0),
                "user_intent": summary.get("user_intent", ""),
                "key_entities": ",".join(summary.get("key_entities", [])),
            },
        )
        try:
            doc_id = self._store.add_documents([doc])[0]
            logger.debug(f"记忆已保存: {doc_id}")
            return doc_id
        except Exception as e:
            logger.warning(f"记忆保存失败: {e}")
            return None

    def search_memories(
        self,
        query: str,
        k: int = 5,
        apply_time_decay: bool = True,
    ) -> list[Document]:
        """
        检索相关记忆

        Args:
            query: 查询文本
            k: 返回数量
            apply_time_decay: 是否应用时间衰减

        Returns:
            按相关性排序的记忆文档列表
        """
        if not self.is_ready() or self._store is None:
            return []

        try:
            docs_with_scores = self._store.similarity_search_with_score(query, k=k * 2)
        except Exception as e:
            logger.warning(f"记忆检索失败: {e}")
            return []

        if not docs_with_scores:
            return []

        # 解码存储的 JSON 内容
        decoded = []
        now = time.time()
        for doc, score in docs_with_scores:
            try:
                content_dict = json.loads(doc.page_content)
                doc.page_content = content_dict.get("user_intent", doc.page_content)
                doc.metadata["memory_data"] = content_dict
                doc.metadata["raw_score"] = round(float(score), 4)
            except json.JSONDecodeError:
                pass

            # 时间衰减
            if apply_time_decay:
                ts = doc.metadata.get("timestamp", 0)
                hours_ago = (now - ts) / 3600
                if hours_ago <= TIME_DECAY_FRESH_HOURS:
                    decay = 1.0
                elif hours_ago <= TIME_DECAY_NORMAL_HOURS:
                    decay = TIME_DECAY_OLD_WEIGHT + 0.4 * (1 - (hours_ago - TIME_DECAY_FRESH_HOURS) / (TIME_DECAY_NORMAL_HOURS - TIME_DECAY_FRESH_HOURS))
                else:
                    decay = TIME_DECAY_OLD_WEIGHT
                doc.metadata["time_decay"] = round(decay, 4)
                doc.metadata["adjusted_score"] = round(float(score) * decay, 4)
            else:
                doc.metadata["adjusted_score"] = round(float(score), 4)

            decoded.append(doc)

        # 按调整后的分数排序
        decoded.sort(key=lambda d: d.metadata.get("adjusted_score", 0), reverse=True)
        return decoded[:k]


# 全局单例
_store: MemoryStore | None = None


def get_memory_store() -> MemoryStore:
    global _store
    if _store is None:
        _store = MemoryStore()
    return _store
