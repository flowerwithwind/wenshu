"""
信息检索评估指标
"""
from __future__ import annotations

import math


def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    return len(set(retrieved[:k]) & relevant) / len(relevant)


def precision_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    if k == 0:
        return 0.0
    return len(set(retrieved[:k]) & relevant) / k


def mrr(retrieved: list[str], relevant: set[str]) -> float:
    for i, doc_id in enumerate(retrieved):
        if doc_id in relevant:
            return 1.0 / (i + 1)
    return 0.0


def ndcg_at_k(retrieved, relevant, graded_relevance=None, k=4):
    if not relevant:
        return 0.0
    actual = [graded_relevance.get(d, 0.0) if graded_relevance else (1.0 if d in relevant else 0.0) for d in retrieved[:k]]
    ideal = sorted([graded_relevance.get(d, 0.0) if graded_relevance else 1.0 for d in retrieved], reverse=True)[:k]
    def dcg(scores):
        return sum(s / math.log2(i + 2) for i, s in enumerate(scores) if i < len(scores))
    idcg = dcg(ideal)
    return dcg(actual) / idcg if idcg > 0 else 0.0


class MetricsCalculator:
    @staticmethod
    def evaluate(retrieved, relevant, k_values=None):
        if k_values is None:
            k_values = [1, 3, 5]
        return {
            **{f"recall@{k}": round(recall_at_k(retrieved, relevant, k), 4) for k in k_values},
            **{f"precision@{k}": round(precision_at_k(retrieved, relevant, k), 4) for k in k_values},
            **{f"ndcg@{k}": round(ndcg_at_k(retrieved, relevant, k=k), 4) for k in k_values},
            "mrr": round(mrr(retrieved, relevant), 4),
        }
