"""
信息检索评估指标

实现:
- Recall@K: Top-K 召回率
- Precision@K: Top-K 精确率
- MRR (Mean Reciprocal Rank): 平均倒数排名
- NDCG@K (Normalized Discounted Cumulative Gain): 归一化折损累计增益
"""
from __future__ import annotations

import math


def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    retrieved_k = set(retrieved[:k])
    hits = len(retrieved_k & relevant)
    return hits / len(relevant)


def precision_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    if k == 0:
        return 0.0
    retrieved_k = set(retrieved[:k])
    hits = len(retrieved_k & relevant)
    return hits / k


def mrr(retrieved: list[str], relevant: set[str]) -> float:
    for i, doc_id in enumerate(retrieved):
        if doc_id in relevant:
            return 1.0 / (i + 1)
    return 0.0


def dcg_at_k(relevance_scores: list[float], k: int) -> float:
    dcg = 0.0
    for i in range(min(k, len(relevance_scores))):
        dcg += relevance_scores[i] / math.log2(i + 2)
    return dcg


def ndcg_at_k(
    retrieved: list[str],
    relevant: set[str],
    graded_relevance: dict[str, float] | None = None,
    k: int = 4,
) -> float:
    if not relevant:
        return 0.0
    if graded_relevance:
        actual_scores = [graded_relevance.get(doc_id, 0.0) for doc_id in retrieved[:k]]
    else:
        actual_scores = [1.0 if doc_id in relevant else 0.0 for doc_id in retrieved[:k]]
    actual_dcg = dcg_at_k(actual_scores, k)
    if graded_relevance:
        ideal_scores = sorted(
            [graded_relevance.get(doc_id, 0.0) for doc_id in retrieved], reverse=True,
        )[:k]
    else:
        ideal_scores = [1.0] * min(len(relevant), k) + [0.0] * max(0, k - len(relevant))
    ideal_dcg = dcg_at_k(ideal_scores, k)
    return actual_dcg / ideal_dcg if ideal_dcg > 0 else 0.0


class MetricsCalculator:
    """评估指标计算器"""

    @staticmethod
    def evaluate(
        retrieved: list[str],
        relevant: set[str],
        k_values: list[int] | None = None,
    ) -> dict[str, float]:
        if k_values is None:
            k_values = [1, 3, 5]
        results: dict[str, float] = {}
        for k in k_values:
            results[f"recall@{k}"] = round(recall_at_k(retrieved, relevant, k), 4)
            results[f"precision@{k}"] = round(precision_at_k(retrieved, relevant, k), 4)
            results[f"ndcg@{k}"] = round(ndcg_at_k(retrieved, relevant, k=k), 4)
        results["mrr"] = round(mrr(retrieved, relevant), 4)
        return results
