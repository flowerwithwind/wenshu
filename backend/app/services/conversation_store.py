"""对话持久化存储 — JSON 文件 + SQLite 索引"""
from __future__ import annotations

import os
import json
import uuid
import sqlite3
from datetime import datetime

STORAGE_DIR: str = os.path.join(os.path.dirname(__file__), '../../data/conversations')
INDEX_DB_PATH: str = os.path.join(os.path.dirname(__file__), '../../data/conversations.db')


class ConversationStore:
    def __init__(self) -> None:
        os.makedirs(STORAGE_DIR, exist_ok=True)
        self._init_index_db()

    def _init_index_db(self) -> None:
        """初始化 SQLite 索引数据库"""
        conn: sqlite3.Connection = sqlite3.connect(INDEX_DB_PATH)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                conversation_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                message_count INTEGER DEFAULT 0,
                last_message TEXT DEFAULT ''
            )
        """)
        conn.commit()
        conn.close()

    def _get_file_path(self, conv_id: str) -> str:
        return os.path.join(STORAGE_DIR, f"{conv_id}.json")

    def create(self, messages: list[dict] | None = None) -> str:
        """创建新对话，返回 conv_id"""
        conv_id: str = str(uuid.uuid4())
        now: str = datetime.now().isoformat()
        data: dict = {
            "conversation_id": conv_id,
            "created_at": now,
            "updated_at": now,
            "messages": messages or [],
        }
        self._save(conv_id, data)
        last_msg: str = messages[-1]["question"][:50] if messages else ""
        conn: sqlite3.Connection = sqlite3.connect(INDEX_DB_PATH)
        conn.execute(
            "INSERT INTO conversations (conversation_id, created_at, updated_at, message_count, last_message) VALUES (?, ?, ?, ?, ?)",
            (conv_id, now, now, len(data["messages"]), last_msg)
        )
        conn.commit()
        conn.close()
        return conv_id

    def add_message(self, conv_id: str, msg: dict) -> None:
        """添加一条消息"""
        conv: dict | None = self.get(conv_id)
        if conv is None:
            conv = {
                "conversation_id": conv_id,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "messages": [],
            }
        conv["messages"].append(msg)
        conv["updated_at"] = datetime.now().isoformat()
        self._save(conv_id, conv)

        last_msg: str = msg.get("question", msg.get("content", ""))[:50]
        conn: sqlite3.Connection = sqlite3.connect(INDEX_DB_PATH)
        conn.execute(
            "INSERT OR REPLACE INTO conversations (conversation_id, created_at, updated_at, message_count, last_message) VALUES (?, ?, ?, ?, ?)",
            (conv_id, conv["created_at"], conv["updated_at"], len(conv["messages"]), last_msg)
        )
        conn.commit()
        conn.close()

    def update_last_message(self, conv_id: str, msg: dict) -> None:
        """更新最后一条消息"""
        conv: dict | None = self.get(conv_id)
        if conv and conv["messages"]:
            conv["messages"][-1] = msg
            conv["updated_at"] = datetime.now().isoformat()
            self._save(conv_id, conv)

            last_msg: str = msg.get("question", msg.get("content", ""))[:50]
            conn: sqlite3.Connection = sqlite3.connect(INDEX_DB_PATH)
            conn.execute(
                "UPDATE conversations SET updated_at = ?, message_count = ?, last_message = ? WHERE conversation_id = ?",
                (conv["updated_at"], len(conv["messages"]), last_msg, conv_id)
            )
            conn.commit()
            conn.close()

    def get(self, conv_id: str) -> dict | None:
        """获取指定对话"""
        file_path: str = self._get_file_path(conv_id)
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def list_all(self) -> list[dict]:
        """获取所有对话摘要列表"""
        conn: sqlite3.Connection = sqlite3.connect(INDEX_DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT conversation_id, created_at, updated_at, message_count, last_message FROM conversations ORDER BY updated_at DESC"
        )
        rows: list[dict] = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows

    def delete(self, conv_id: str) -> bool:
        """删除指定对话"""
        file_path: str = self._get_file_path(conv_id)
        deleted: bool = False
        if os.path.exists(file_path):
            os.remove(file_path)
            deleted = True

        conn: sqlite3.Connection = sqlite3.connect(INDEX_DB_PATH)
        conn.execute("DELETE FROM conversations WHERE conversation_id = ?", (conv_id,))
        conn.commit()
        conn.close()
        return deleted

    def clear(self) -> int:
        """清空所有对话"""
        count: int = 0
        for fname in os.listdir(STORAGE_DIR):
            if fname.endswith(".json"):
                os.remove(os.path.join(STORAGE_DIR, fname))
                count += 1

        conn: sqlite3.Connection = sqlite3.connect(INDEX_DB_PATH)
        conn.execute("DELETE FROM conversations")
        conn.commit()
        conn.close()
        return count

    def _save(self, conv_id: str, data: dict) -> None:
        """保存对话到 JSON 文件"""
        file_path: str = self._get_file_path(conv_id)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


# 全局单例
_store: ConversationStore | None = None


def get_conversation_store() -> ConversationStore:
    global _store
    if _store is None:
        _store = ConversationStore()
    return _store
