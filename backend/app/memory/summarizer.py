"""
对话摘要模块

功能：
1. 监听对话轮次，每 5 轮自动触发摘要
2. 使用 LLM 对历史对话生成结构化摘要
3. 摘要包含：用户意图、关键实体、执行SQL、重要事实、用户偏好

存储到 SQLite 的 memory_summaries 表。
"""
from __future__ import annotations

import json
import sqlite3
import time
from typing import Any
from pathlib import Path

from app.logger import get_logger

logger = get_logger(__name__)

MEMORY_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "memory.db"

SUMMARIZE_INTERVAL = 5  # 每 5 轮对话摘要一次

# 默认摘要提示词
SUMMARIZE_PROMPT = """请对以下对话历史进行结构化摘要，提炼关键信息。

对话历史：
{conversation_history}

请以 JSON 格式输出：
{{
    "user_intent": "用户的整体意图",
    "key_entities": ["关键实体1", "关键实体2"],
    "sql_executed": "执行的SQL（如有）",
    "important_facts": ["重要事实1", "重要事实2"],
    "user_preferences": ["用户偏好1"]
}}
"""


class ConversationSummarizer:
    """对话摘要生成器"""

    def __init__(self, llm=None) -> None:
        """
        Args:
            llm: LLM 实例（可选，None 时会尝试从 app.models.provider 获取）
        """
        self.llm = llm
        self._init_db()

    def _init_db(self) -> None:
        """初始化记忆数据库表"""
        MEMORY_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(MEMORY_DB_PATH))
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    turn_count INTEGER NOT NULL,
                    created_at REAL NOT NULL,
                    embedding_id TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_memory_conv
                ON memory_summaries(conversation_id)
            """)
            conn.commit()
        finally:
            conn.close()

    def should_summarize(self, conversation_id: str, current_turn: int) -> bool:
        """判断是否需要生成摘要"""
        if current_turn <= 0:
            return False
        return current_turn % SUMMARIZE_INTERVAL == 0

    def summarize(
        self,
        conversation_id: str,
        history: list[dict[str, str]],
        turn_count: int,
    ) -> dict[str, Any] | None:
        """
        生成对话摘要并存储

        Args:
            conversation_id: 对话 ID
            history: 对话历史列表 [{"role": "user/assistant", "content": "..."}]
            turn_count: 当前对话轮次

        Returns:
            摘要数据字典，或 None（生成失败时）
        """
        if not self.should_summarize(conversation_id, turn_count):
            return None

        # 构造摘要提示
        history_text = self._format_history(history)
        prompt = SUMMARIZE_PROMPT.format(conversation_history=history_text)

        # 调用 LLM 生成摘要
        summary_data = self._call_llm(prompt)
        if not summary_data:
            logger.warning(f"对话摘要生成失败: {conversation_id}")
            return None

        # 存储到数据库
        self._save_summary(conversation_id, summary_data, turn_count)
        logger.info(f"对话摘要已保存: conv={conversation_id}, turn={turn_count}")
        return summary_data

    def get_summaries(
        self,
        conversation_id: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """获取指定对话的历史摘要"""
        conn = sqlite3.connect(str(MEMORY_DB_PATH))
        try:
            rows = conn.execute(
                "SELECT summary, turn_count, created_at FROM memory_summaries "
                "WHERE conversation_id = ? ORDER BY created_at DESC LIMIT ?",
                (conversation_id, limit),
            ).fetchall()

            results = []
            for row in rows:
                try:
                    summary = json.loads(row[0])
                    summary["turn_count"] = row[1]
                    summary["created_at"] = row[2]
                    results.append(summary)
                except json.JSONDecodeError:
                    continue
            return results
        finally:
            conn.close()

    def get_all_summaries(self, limit: int = 50) -> list[dict[str, Any]]:
        """获取所有摘要（用于跨对话记忆检索）"""
        conn = sqlite3.connect(str(MEMORY_DB_PATH))
        try:
            rows = conn.execute(
                "SELECT conversation_id, summary, turn_count, created_at "
                "FROM memory_summaries ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()

            results = []
            for row in rows:
                try:
                    summary = json.loads(row[1])
                    summary["conversation_id"] = row[0]
                    summary["turn_count"] = row[2]
                    summary["created_at"] = row[3]
                    results.append(summary)
                except json.JSONDecodeError:
                    continue
            return results
        finally:
            conn.close()

    # -------- 内部方法 --------

    def _format_history(self, history: list[dict[str, str]]) -> str:
        """格式化对话历史为文本"""
        lines = []
        for msg in history[-SUMMARIZE_INTERVAL * 2:]:  # 只取最近 N 条
            role = msg.get("role", "unknown")
            content = msg.get("content", "")[:500]
            lines.append(f"[{role}]: {content}")
        return "\n".join(lines)

    def _call_llm(self, prompt: str) -> dict[str, Any] | None:
        """调用 LLM 生成摘要"""
        if self.llm is None:
            try:
                from app.models.provider import get_chat_model
                self.llm = get_chat_model(temperature=0.1, max_tokens=1024)
            except Exception as e:
                logger.warning(f"LLM 未配置，无法生成摘要: {e}")
                return None

        try:
            response = self.llm.invoke(prompt)
            content = response.content if hasattr(response, "content") else str(response)
            # 提取 JSON
            content = content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("\n", 1)[0]
            return json.loads(content)
        except Exception as e:
            logger.warning(f"LLM 摘要生成异常: {e}")
            return None

    def _save_summary(
        self,
        conversation_id: str,
        summary_data: dict[str, Any],
        turn_count: int,
    ) -> None:
        """保存摘要到数据库"""
        conn = sqlite3.connect(str(MEMORY_DB_PATH))
        try:
            conn.execute(
                "INSERT INTO memory_summaries (conversation_id, summary, turn_count, created_at) "
                "VALUES (?, ?, ?, ?)",
                (conversation_id, json.dumps(summary_data, ensure_ascii=False), turn_count, time.time()),
            )
            conn.commit()
        finally:
            conn.close()


# 全局单例
_summarizer: ConversationSummarizer | None = None


def get_summarizer() -> ConversationSummarizer:
    global _summarizer
    if _summarizer is None:
        _summarizer = ConversationSummarizer()
    return _summarizer
