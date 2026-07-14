"""NL2SQL 知识库 CRUD — 按数据源隔离"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.config import BACKEND_ROOT, DATASET_DIR
from app.datasources.sqlite_ds import BUILTIN_SQLITE_ID
from app.logger import get_logger

logger = get_logger(__name__)

# 内置电商库沿用原路径，便于兼容
BUILTIN_KNOWLEDGE_PATH: str = os.path.join(DATASET_DIR, "nl2sql_knowledge.json")
KNOWLEDGE_ROOT: Path = BACKEND_ROOT / "data" / "knowledge"


def _empty_knowledge() -> dict[str, Any]:
    return {
        "question_sql_examples": [],
        "synonym_mappings": [],
        "domain_mappings": [],
        "table_schemas": [],
    }


def knowledge_path(datasource_id: str | None = None) -> Path:
    """解析知识库文件路径（按数据源隔离）。"""
    ds_id = (datasource_id or BUILTIN_SQLITE_ID).strip() or BUILTIN_SQLITE_ID
    if ds_id == BUILTIN_SQLITE_ID:
        return Path(BUILTIN_KNOWLEDGE_PATH)
    KNOWLEDGE_ROOT.mkdir(parents=True, exist_ok=True)
    return KNOWLEDGE_ROOT / f"{ds_id}.json"


def load_knowledge(datasource_id: str | None = None) -> dict[str, Any]:
    path = knowledge_path(datasource_id)
    if not path.exists():
        data = _empty_knowledge()
        # 非内置库首次访问时落盘空模板
        if (datasource_id or BUILTIN_SQLITE_ID) != BUILTIN_SQLITE_ID:
            save_knowledge(data, datasource_id)
        return data
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, dict):
        return _empty_knowledge()
    for k, v in _empty_knowledge().items():
        raw.setdefault(k, v if not isinstance(v, list) else [])
    return raw


def save_knowledge(data: dict[str, Any], datasource_id: str | None = None) -> None:
    path = knowledge_path(datasource_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def knowledge_as_prompt_context(datasource_id: str | None = None, limit: int = 6) -> str:
    """将当前数据源知识库压成 NL2SQL 可用的文本上下文。"""
    data = load_knowledge(datasource_id)
    parts: list[str] = []
    examples = data.get("question_sql_examples") or []
    for ex in examples[:limit]:
        parts.append(f"【示例问题】{ex.get('question', '')}")
        parts.append(f"【对应SQL】{ex.get('sql', '')}")
        if ex.get("tables"):
            parts.append(f"【涉及表】{', '.join(ex.get('tables') or [])}")
    for syn in (data.get("synonym_mappings") or [])[:20]:
        parts.append(
            f"【同义词】{', '.join(syn.get('synonyms') or [])} → {syn.get('table')}.{syn.get('target_column')}"
        )
    for dm in (data.get("domain_mappings") or [])[:20]:
        parts.append(
            f"【领域术语】{dm.get('term')} => {dm.get('mapping')} (表:{dm.get('applicable_table') or dm.get('table')})"
        )
    return "\n".join(parts)


def add_example(
    question: str,
    sql: str,
    tables: list[str],
    tags: list[str],
    datasource_id: str | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = load_knowledge(datasource_id)
    example: dict[str, Any] = {
        "question": question,
        "sql": sql,
        "tables": tables,
        "tags": tags,
    }
    data.setdefault("question_sql_examples", []).append(example)
    save_knowledge(data, datasource_id)
    return {"index": len(data["question_sql_examples"]) - 1, "example": example}


def delete_example(index: int, datasource_id: str | None = None) -> bool:
    data: dict[str, Any] = load_knowledge(datasource_id)
    examples: list[dict[str, Any]] = data.get("question_sql_examples", [])
    if 0 <= index < len(examples):
        examples.pop(index)
        save_knowledge(data, datasource_id)
        return True
    return False


def update_example(index: int, datasource_id: str | None = None, **kwargs: Any) -> dict[str, Any]:
    data: dict[str, Any] = load_knowledge(datasource_id)
    examples: list[dict[str, Any]] = data.get("question_sql_examples", [])
    if 0 <= index < len(examples):
        for key in ("question", "sql", "tables", "tags"):
            if key in kwargs:
                examples[index][key] = kwargs[key]
        save_knowledge(data, datasource_id)
        return examples[index]
    raise IndexError(f"索引 {index} 超出范围")


def add_synonym(
    synonyms: list[str],
    target_column: str,
    table: str,
    datasource_id: str | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = load_knowledge(datasource_id)
    entry: dict[str, Any] = {
        "synonyms": synonyms,
        "target_column": target_column,
        "table": table,
    }
    data.setdefault("synonym_mappings", []).append(entry)
    save_knowledge(data, datasource_id)
    return {"index": len(data["synonym_mappings"]) - 1, "entry": entry}


def delete_synonym(index: int, datasource_id: str | None = None) -> bool:
    data: dict[str, Any] = load_knowledge(datasource_id)
    mappings: list[dict[str, Any]] = data.get("synonym_mappings", [])
    if 0 <= index < len(mappings):
        mappings.pop(index)
        save_knowledge(data, datasource_id)
        return True
    return False


def add_domain_mapping(
    term: str,
    mapping: str,
    table: str,
    datasource_id: str | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = load_knowledge(datasource_id)
    entry: dict[str, Any] = {
        "term": term,
        "mapping": mapping,
        "applicable_table": table,
    }
    data.setdefault("domain_mappings", []).append(entry)
    save_knowledge(data, datasource_id)
    return {"index": len(data["domain_mappings"]) - 1, "entry": entry}


def delete_domain_mapping(index: int, datasource_id: str | None = None) -> bool:
    data: dict[str, Any] = load_knowledge(datasource_id)
    mappings: list[dict[str, Any]] = data.get("domain_mappings", [])
    if 0 <= index < len(mappings):
        mappings.pop(index)
        save_knowledge(data, datasource_id)
        return True
    return False


def get_stats(datasource_id: str | None = None) -> dict[str, Any]:
    data: dict[str, Any] = load_knowledge(datasource_id)
    return {
        "examples_count": len(data.get("question_sql_examples", [])),
        "synonyms_count": len(data.get("synonym_mappings", [])),
        "domain_mappings_count": len(data.get("domain_mappings", [])),
        "table_schemas_count": len(data.get("table_schemas", [])),
        "datasource_id": datasource_id or BUILTIN_SQLITE_ID,
    }
