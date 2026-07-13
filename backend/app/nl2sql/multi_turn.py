"""多轮对话上下文管理器"""
from __future__ import annotations

MAX_CONTEXT_TURNS: int = 6  # 最多保留最近 6 轮对话


class ConversationContext:
    """管理单次对话的上下文"""

    def __init__(self, conversation_id: str) -> None:
        self.conversation_id: str = conversation_id
        self.turns: list[dict[str, str]] = []  # [{question, sql, answer_summary}]

    def add_turn(self, question: str, sql: str, answer: str) -> None:
        """添加一轮对话。answer 截断到 200 字符作为摘要"""
        self.turns.append({
            "question": question,
            "sql": sql,
            "answer_summary": answer[:200] if answer else "",
        })
        # 保留最近 N 轮
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


class MultiTurnManager:
    """管理所有对话的上下文"""

    def __init__(self) -> None:
        self._contexts: dict[str, ConversationContext] = {}

    def get_context(self, conv_id: str) -> ConversationContext:
        if conv_id not in self._contexts:
            self._contexts[conv_id] = ConversationContext(conv_id)
        return self._contexts[conv_id]

    def remove_context(self, conv_id: str) -> None:
        self._contexts.pop(conv_id, None)

    def clear_all(self) -> int:
        count: int = len(self._contexts)
        self._contexts.clear()
        return count


# 全局单例
_manager: MultiTurnManager | None = None


def get_multi_turn_manager() -> MultiTurnManager:
    global _manager
    if _manager is None:
        _manager = MultiTurnManager()
    return _manager
