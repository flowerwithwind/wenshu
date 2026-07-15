"""
Embedding 模型微调前后效果对比

对比基座模型与微调模型在评测集上的 Recall@K 和 MRR。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

BENCHMARK_PATH = BACKEND_ROOT / "data" / "evaluation" / "benchmark.json"
BASE_MODEL = "BAAI/bge-large-zh-v1.5"
FINETUNED_MODEL = BACKEND_ROOT / "data" / "models" / "finetuned-bge"


def load_benchmark() -> list[dict]:
    """加载评测集"""
    if not BENCHMARK_PATH.exists():
        print(f"[ERROR] 评测集不存在: {BENCHMARK_PATH}")
        return []
    with open(BENCHMARK_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def compute_metrics(
    model,
    queries: list[str],
    candidate_docs: list[dict],
    k_values: list[int] = None,
) -> dict[str, float]:
    """计算检索指标"""
    if k_values is None:
        k_values = [1, 3, 5]

    from sentence_transformers import util
    import numpy as np

    # 编码
    query_emb = model.encode(queries, normalize_embeddings=True)
    doc_emb = model.encode(
        [d["content"] for d in candidate_docs],
        normalize_embeddings=True,
    )

    all_recalls = {k: [] for k in k_values}
    all_mrrs = []

    for i, q in enumerate(queries):
        # 计算相似度
        scores = util.cos_sim(query_emb[i], doc_emb)[0]
        sorted_indices = scores.argsort(descending=True)

        # 找相关文档（包含查询关键词的文档）
        query_keywords = set(q.lower().split())
        relevant_indices = set()
        for j, doc in enumerate(candidate_docs):
            content = doc["content"].lower()
            if any(kw in content for kw in query_keywords):
                relevant_indices.add(j)

        if not relevant_indices:
            continue

        retrieved = [idx.item() for idx in sorted_indices]

        # Recall@K
        for k in k_values:
            hits = len(set(retrieved[:k]) & relevant_indices)
            all_recalls[k].append(hits / len(relevant_indices))

        # MRR
        for rank, idx in enumerate(retrieved):
            if idx in relevant_indices:
                all_mrrs.append(1.0 / (rank + 1))
                break
        else:
            all_mrrs.append(0.0)

    metrics = {}
    for k in k_values:
        metrics[f"Recall@{k}"] = round(np.mean(all_recalls[k]), 4) if all_recalls[k] else 0.0
    metrics["MRR"] = round(np.mean(all_mrrs), 4) if all_mrrs else 0.0
    return metrics


def main():
    benchmark = load_benchmark()
    if not benchmark:
        return

    queries = [item["question"] for item in benchmark]
    candidate_docs = [
        {
            "content": f"{item['question']} - {' '.join(item.get('expected_answer_contains', []))}",
            "id": item["id"],
        }
        for item in benchmark
    ]

    from sentence_transformers import SentenceTransformer

    print("=" * 60)
    print("Embedding 模型微调前后对比")
    print("=" * 60)

    # 基座模型
    print(f"\n[基座模型] {BASE_MODEL}")
    try:
        base_model = SentenceTransformer(BASE_MODEL)
        base_metrics = compute_metrics(base_model, queries, candidate_docs)
        for k, v in base_metrics.items():
            print(f"  {k}: {v:.4f}")
    except Exception as e:
        print(f"  加载失败: {e}")
        base_metrics = {}

    # 微调模型
    finetuned_path = str(FINETUNED_MODEL)
    if os.path.exists(finetuned_path):
        print(f"\n[微调模型] {finetuned_path}")
        try:
            ft_model = SentenceTransformer(finetuned_path)
            ft_metrics = compute_metrics(ft_model, queries, candidate_docs)
            for k, v in ft_metrics.items():
                print(f"  {k}: {v:.4f}")
        except Exception as e:
            print(f"  加载失败: {e}")
            ft_metrics = {}
    else:
        print(f"\n[微调模型] 不存在，跳过对比")
        print("请先运行: python scripts/finetune_embedding.py --train")
        ft_metrics = {}

    # 对比
    if base_metrics and ft_metrics:
        print("\n" + "-" * 40)
        print("提升幅度:")
        for metric in base_metrics:
            diff = ft_metrics.get(metric, 0) - base_metrics[metric]
            symbol = "+" if diff >= 0 else ""
            print(f"  {metric}: {symbol}{diff:.4f}")


if __name__ == "__main__":
    main()
