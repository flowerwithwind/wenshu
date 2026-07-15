"""
记忆感知检索器

将 RAG 知识库检索与对话记忆检索融合，使 Agent 能感知历史上下文。

检索策略：
1. RAG 知识库（领域知识）
2. 对话记忆库（历史上下文）
3. 结果融合 → 注入 System Prompt
"""
from __future__ import annotations

from typing import Any
from langchain_core.documents import Document
from app.memory.store import MemoryStore, get_memory_store
from app.logger import get_logger

logger = get_logger(__name__)


class MemoryRetriever:
    """记忆感知检索器"""

    def __init__(self, memory_store: MemoryStore | None = None) -> None:
        self.store = memory_store or get_memory_store()

    def retrieve_memory_context(
        self,
        query: str,
        conversation_id: str | None = None,
        k: int = 3,
    ) -> str:
        """
        检索历史记忆，格式化为上下文字符串

        Args:
            query: 当前用户问题
            conversation_id: 当前对话 ID
            k: 返回记忆条数

        Returns:
            格式化的记忆上下文字符串，可直接注入 System Prompt
        """
        memory_docs = self.store.search_memories(query, k=k)
        if not memory_docs:
            return ""

        context_parts = ["【历史对话记忆】"]
        for i, doc in enumerate(memory_docs):
            md = doc.metadata
            memory_data = md.get("memory_data", {})
            intent = memory_data.get("user_intent", "") or doc.page_content[:100]
            facts = memory_data.get("important_facts", [])
            preferences = memory_data.get("user_preferences", [])

            entry = f"[记忆 {i+1}] {intent}"
            if facts:
                entry += f"\n  关键事实: {'; '.join(facts[:2])}"
            if preferences:
                entry += f"\n  用户偏好: {'; '.join(preferences[:2])}"
            context_parts.append(entry)

        return "\n\n".join(context_parts)

    def format_memory_prompt(self, query: str) -> str:
        """
        生成完整的记忆增强提示段

        用法：将返回值直接追加到 Agent 的 System Prompt 末尾
        """
        memory_context = self.retrieve_memory_context(query)
        if not memory_context:
            return ""
        return f"\n\n{memory_context}"


# 全局单例
_retriever: MemoryRetriever | None = None


def get_memory_retriever() -> MemoryRetriever:
    global _retriever
    if _retriever is None:
        _retriever = MemoryRetriever()
    return _retriever
