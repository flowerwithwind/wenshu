"""NL2SQL 知识库 CRUD 管理"""
from __future__ import annotations

import os
import json
from typing import Any

from app.config import DATASET_DIR

KNOWLEDGE_PATH: str = os.path.join(DATASET_DIR, "nl2sql_knowledge.json")


def load_knowledge() -> dict[str, Any]:
    with open(KNOWLEDGE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_knowledge(data: dict[str, Any]) -> None:
    with open(KNOWLEDGE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add_example(question: str, sql: str, tables: list[str], tags: list[str]) -> dict[str, Any]:
    """添加一条 Few-shot 示例"""
    data: dict[str, Any] = load_knowledge()
    example: dict[str, Any] = {
        "question": question,
        "sql": sql,
        "tables": tables,
        "tags": tags,
    }
    data.setdefault("question_sql_examples", []).append(example)
    save_knowledge(data)
    return {"index": len(data["question_sql_examples"]) - 1, "example": example}


def delete_example(index: int) -> bool:
    """删除指定索引的示例"""
    data: dict[str, Any] = load_knowledge()
    examples: list[dict[str, Any]] = data.get("question_sql_examples", [])
    if 0 <= index < len(examples):
        examples.pop(index)
        save_knowledge(data)
        return True
    return False


def update_example(index: int, **kwargs: Any) -> dict[str, Any]:
    """更新一条示例"""
    data: dict[str, Any] = load_knowledge()
    examples: list[dict[str, Any]] = data.get("question_sql_examples", [])
    if 0 <= index < len(examples):
        for key in ("question", "sql", "tables", "tags"):
            if key in kwargs:
                examples[index][key] = kwargs[key]
        save_knowledge(data)
        return examples[index]
    raise IndexError(f"索引 {index} 超出范围")


def add_synonym(synonyms: list[str], target_column: str, table: str) -> dict[str, Any]:
    """添加同义词映射"""
    data: dict[str, Any] = load_knowledge()
    entry: dict[str, Any] = {
        "synonyms": synonyms,
        "target_column": target_column,
        "table": table,
    }
    data.setdefault("synonym_mappings", []).append(entry)
    save_knowledge(data)
    return {"index": len(data["synonym_mappings"]) - 1, "entry": entry}


def delete_synonym(index: int) -> bool:
    """删除指定索引的同义词"""
    data: dict[str, Any] = load_knowledge()
    mappings: list[dict[str, Any]] = data.get("synonym_mappings", [])
    if 0 <= index < len(mappings):
        mappings.pop(index)
        save_knowledge(data)
        return True
    return False


def add_domain_mapping(term: str, mapping: str, table: str) -> dict[str, Any]:
    """添加领域术语映射"""
    data: dict[str, Any] = load_knowledge()
    entry: dict[str, Any] = {
        "term": term,
        "mapping": mapping,
        "applicable_table": table,
    }
    data.setdefault("domain_mappings", []).append(entry)
    save_knowledge(data)
    return {"index": len(data["domain_mappings"]) - 1, "entry": entry}


def delete_domain_mapping(index: int) -> bool:
    """删除指定索引的领域映射"""
    data: dict[str, Any] = load_knowledge()
    mappings: list[dict[str, Any]] = data.get("domain_mappings", [])
    if 0 <= index < len(mappings):
        mappings.pop(index)
        save_knowledge(data)
        return True
    return False


def get_stats() -> dict[str, int]:
    """知识库统计: 示例数、同义词数、领域映射数、表数"""
    data: dict[str, Any] = load_knowledge()
    return {
        "examples_count": len(data.get("question_sql_examples", [])),
        "synonyms_count": len(data.get("synonym_mappings", [])),
        "domain_mappings_count": len(data.get("domain_mappings", [])),
        "table_schemas_count": len(data.get("table_schemas", [])),
    }
