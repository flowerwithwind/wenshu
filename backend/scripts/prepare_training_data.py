"""
训练数据准备脚本 - 从 NL2SQL 知识库构建 Embedding 微调数据

输出: data/training/train_triplets.json (query, positive, negative 三元组)
"""
from __future__ import annotations

import json
import os
import random
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
DATASET_DIR = BACKEND_ROOT / "data" / "datasets"
OUTPUT_DIR = BACKEND_ROOT / "data" / "training"
KNOWLEDGE_PATH = DATASET_DIR / "nl2sql_knowledge.json"


def load_knowledge() -> dict:
    """加载 NL2SQL 知识库"""
    if not KNOWLEDGE_PATH.exists():
        print(f"[ERROR] 知识库文件不存在: {KNOWLEDGE_PATH}")
        return {}
    with open(KNOWLEDGE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def build_triplets(knowledge: dict) -> list[dict]:
    """构建 (query, positive, negative) 三元组"""
    triplets = []
    examples = knowledge.get("question_sql_examples", [])
    schemas = knowledge.get("table_schemas", [])
    mappings = knowledge.get("domain_mappings", [])
    synonyms = knowledge.get("synonym_mappings", [])

    all_docs = []

    # 从 Question-SQL 示例构建
    for ex in examples:
        content = f"【示例问题】{ex['question']}\n【对应SQL】{ex['sql']}"
        tags = ex.get("tags", [])
        all_docs.append({
            "content": content,
            "tags": set(tags),
            "type": "example",
            "tables": set(ex.get("tables", [])),
            "id": f"example_{ex.get('question', '')[:20]}",
        })

    # 从表结构构建
    for schema in schemas:
        col_lines = [f"  - {c['name']}({c['type']}): {c['description']}" for c in schema.get("columns", [])]
        content = f"【数据表】{schema['table']}\n【描述】{schema['description']}\n【列信息】\n" + "\n".join(col_lines)
        all_docs.append({
            "content": content,
            "tags": set(),
            "type": "schema",
            "tables": {schema["table"]},
            "id": f"schema_{schema['table']}",
        })

    # 从领域映射构建
    for m in mappings:
        content = f"【领域术语】{m['term']} → {m['mapping']}"
        all_docs.append({
            "content": content,
            "tags": set(),
            "type": "domain",
            "tables": {m.get("applicable_table", "")},
            "id": f"domain_{m['term']}",
        })

    # 从同义词构建
    for s in synonyms:
        content = f"【同义词】{', '.join(s['synonyms'])} → {s['target_column']}"
        all_docs.append({
            "content": content,
            "tags": set(),
            "type": "synonym",
            "tables": {s.get("table", "")},
            "id": f"synonym_{s['target_column']}",
        })

    print(f"共 {len(all_docs)} 个文档")

    # 构建三元组：对每个 Question，将对应的文档作为 positive，随机选不同类别的作为 negative
    for i, ex in enumerate(examples):
        query = ex["question"]
        ex_tables = set(ex.get("tables", []))
        ex_tags = set(ex.get("tags", []))

        # 找 positive：与当前问题共享表或标签的文档
        positives = [
            doc for doc in all_docs
            if (doc["tables"] & ex_tables) or (doc["tags"] & ex_tags)
        ]
        # 如果没有共享标签的，用当前问题的示例本身
        if not positives:
            positives = [all_docs[i]] if i < len(all_docs) else []

        # 找 negative：与当前问题无任何共享表或标签的文档
        negatives = [
            doc for doc in all_docs
            if not (doc["tables"] & ex_tables) and not (doc["tags"] & ex_tags)
            and doc["id"] != f"example_{ex['question'][:20]}"
        ]

        if positives and negatives:
            pos = random.choice(positives)
            neg = random.choice(negatives)
            triplets.append({
                "query": query,
                "positive": pos["content"],
                "negative": neg["content"],
                "positive_type": pos["type"],
                "negative_type": neg["type"],
            })

    return triplets


def main():
    knowledge = load_knowledge()
    if not knowledge:
        return

    triplets = build_triplets(knowledge)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output_path = OUTPUT_DIR / "train_triplets.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(triplets, f, ensure_ascii=False, indent=2)

    print(f"训练数据已保存: {output_path}")
    print(f"三元组数量: {len(triplets)}")

    # 简单统计
    pos_types = {}
    for t in triplets:
        pt = t["positive_type"]
        pos_types[pt] = pos_types.get(pt, 0) + 1
    print(f"正例类型分布: {pos_types}")


if __name__ == "__main__":
    main()
