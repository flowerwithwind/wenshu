"""
金标数据集加载器

从 benchmark.json 加载评测数据，提供统一的访问接口。
"""
from __future__ import annotations

import json
import os
from typing import Any

from app.logger import get_logger

logger = get_logger(__name__)

BENCHMARK_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data", "evaluation", "benchmark.json",
)


class BenchmarkItem:
    """单条评测数据"""

    def __init__(self, data: dict[str, Any]) -> None:
        self.id: str = data["id"]
        self.question: str = data["question"]
        self.category: str = data.get("category", "sql_generation")
        self.expected_sql_contains: list[str] = data.get("expected_sql_contains", [])
        self.expected_answer_contains: list[str] = data.get("expected_answer_contains", [])
        self.relevant_doc_keywords: list[str] = data.get("relevant_doc_keywords", [])

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "question": self.question,
            "category": self.category,
            "expected_sql_contains": self.expected_sql_contains,
            "expected_answer_contains": self.expected_answer_contains,
            "relevant_doc_keywords": self.relevant_doc_keywords,
        }


class BenchmarkLoader:
    """金标数据集加载器"""

    def __init__(self, path: str = BENCHMARK_PATH) -> None:
        self.path: str = path
        self._items: list[BenchmarkItem] = []
        self._loaded: bool = False

    def load(self) -> list[BenchmarkItem]:
        """加载评测集"""
        if self._loaded:
            return self._items

        if not os.path.exists(self.path):
            logger.warning(f"评测集文件不存在: {self.path}")
            return []

        try:
            with open(self.path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)

            self._items = [BenchmarkItem(item) for item in raw_data]
            self._loaded = True
            logger.info(f"评测集加载完成: {len(self._items)} 条")
            return self._items
        except Exception as e:
            logger.error(f"评测集加载失败: {e}")
            return []

    @property
    def items(self) -> list[BenchmarkItem]:
        return self._items if self._loaded else self.load()

    @property
    def count(self) -> int:
        return len(self.items)

    def get_by_category(self, category: str) -> list[BenchmarkItem]:
        """按分类筛选"""
        return [item for item in self.items if item.category == category]
