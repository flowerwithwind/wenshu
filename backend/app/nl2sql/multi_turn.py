"""多轮对话上下文管理器 — 支持从持久化对话恢复"""
from __future__ import annotations

from app.logger import get_logger

logger = get_logger(__name__)

MAX_CONTEXT_TURNS: int = 6  # 最多保留最近 6 轮对话


class ConversationContext:
    """管理单次对话的上下文"""

    def __init__(self, conversation_id: str) -> None:
        self.conversation_id: str = conversation_id
        self.turns: list[dict[str, str]] = []  # [{question, sql, answer_summary}]
        self._hydrated: bool = False

    def add_turn(self, question: str, sql: str, answer: str) -> None:
        """添加一轮对话。answer 截断到 200 字符作为摘要"""
        self.turns.append({
            "question": question,
            "sql": sql or "",
            "answer_summary": answer[:200] if answer else "",
        })
        if len(self.turns) > MAX_CONTEXT_TURNS:
            self.turns = self.turns[-MAX_CONTEXT_TURNS:]

    def get_context_prompt(self) -> str:
        """生成注入到 NL2SQL Prompt 的上下文文本"""
        if not self.turns:
            return ""
        lines: list[str] = ["## 对话历史（按时间顺序，用于理解指代和追问）"]
        for i, turn in enumerate(self.turns, 1):
            lines.append(f"{i}. 用户问: {turn['question']}")
            lines.append(f"   SQL: {turn['sql'][:150]}")
            lines.append(f"   回答: {turn['answer_summary']}")
        return "\n".join(lines)

    def hydrate_from_messages(self, messages: list[dict]) -> None:
        """从持久化消息列表恢复上下文（仅首次）"""
        if self._hydrated or self.turns:
            self._hydrated = True
            return
        for msg in messages:
            question: str = msg.get("question") or ""
            if not question:
                continue
            self.add_turn(
                question=question,
                sql=msg.get("sql") or "",
                answer=msg.get("answer") or "",
            )
        self._hydrated = True
        if self.turns:
            logger.debug(
                f"多轮上下文已从持久化恢复: conv={self.conversation_id}, turns={len(self.turns)}"
            )


class MultiTurnManager:
    """管理所有对话的上下文"""

    def __init__(self) -> None:
        self._contexts: dict[str, ConversationContext] = {}

    def get_context(self, conv_id: str, hydrate: bool = True) -> ConversationContext:
        """获取对话上下文；可选从 conversation_store 恢复历史"""
        if conv_id not in self._contexts:
            ctx = ConversationContext(conv_id)
            if hydrate:
                self._try_hydrate(ctx)
            self._contexts[conv_id] = ctx
        elif hydrate and not self._contexts[conv_id]._hydrated:
            self._try_hydrate(self._contexts[conv_id])
        return self._contexts[conv_id]

    def _try_hydrate(self, ctx: ConversationContext) -> None:
        """尝试从持久化存储恢复上下文"""
        try:
            from app.services.conversation_store import get_conversation_store

            conv: dict | None = get_conversation_store().get(ctx.conversation_id)
            if conv and conv.get("messages"):
                ctx.hydrate_from_messages(conv["messages"])
            else:
                ctx._hydrated = True
        except Exception as e:
            logger.warning(f"多轮上下文恢复失败: {e}")
            ctx._hydrated = True

    def remove_context(self, conv_id: str) -> None:
        self._contexts.pop(conv_id, None)

    def clear_all(self) -> int:
        count: int = len(self._contexts)
        self._contexts.clear()
        return count


_manager: MultiTurnManager | None = None


def get_multi_turn_manager() -> MultiTurnManager:
    global _manager
    if _manager is None:
        _manager = MultiTurnManager()
    return _manager
