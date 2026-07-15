"""
评估对比运行器

支持策略对比：
1. 纯语义检索 (SmartRetriever)
2. BM25 关键词检索
3. 混合检索 (HybridRetriever)
4. 混合检索+精排 (HybridRetriever + CrossEncoder)
"""
from __future__ import annotations

import time
import uuid
from typing import Any

from langchain_core.documents import Document
from app.evaluation.benchmark import BenchmarkLoader, BenchmarkItem
from app.evaluation.metrics import MetricsCalculator
from app.rag.pipeline import RAGPipeline
from app.logger import get_logger

logger = get_logger(__name__)


class EvaluationRunner:
    """评估对比运行器"""

    def __init__(self, pipeline: RAGPipeline) -> None:
        self.pipeline = pipeline
        self.benchmark = BenchmarkLoader()
        self.metrics = MetricsCalculator()

    def run_all(self, strategies: list[str] | None = None) -> dict[str, Any]:
        if strategies is None:
            strategies = ["semantic", "bm25", "hybrid", "hybrid_reranked"]
        items = self.benchmark.load()
        if not items:
            return {"error": "评测集为空", "details": {}}
        results: dict[str, dict[str, float]] = {}
        for strategy in strategies:
            strategy_results = self._run_strategy(strategy, items)
            results[strategy] = {k: round(v, 4) for k, v in strategy_results.items()}
        best = self._find_best(results)
        return {
            "eval_id": str(uuid.uuid4()),
            "total_items": len(items),
            "strategies": strategies,
            "results": results,
            "best_strategy": best,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }

    def _run_strategy(self, strategy: str, items: list[BenchmarkItem]) -> dict[str, float]:
        all_metrics: dict[str, list[float]] = {
            "recall@1": [], "recall@3": [], "recall@5": [],
            "precision@1": [], "precision@3": [], "precision@5": [],
            "mrr": [], "ndcg@1": [], "ndcg@3": [], "ndcg@5": [],
        }
        for item in items:
            retrieved_docs = self._retrieve(strategy, item.question, k=5)
            retrieved_ids = self._doc_ids(retrieved_docs)
            relevant_ids = self._get_relevant_ids(item, retrieved_docs)
            eval_result = self.metrics.evaluate(retrieved_ids, relevant_ids)
            for metric, value in eval_result.items():
                if metric in all_metrics:
                    all_metrics[metric].append(value)
        avg_metrics = {}
        for metric, values in all_metrics.items():
            avg_metrics[metric] = round(sum(values) / len(values), 4) if values else 0.0
        return avg_metrics

    def _retrieve(self, strategy: str, query: str, k: int = 5) -> list[Document]:
        try:
            if strategy == "semantic" and self.pipeline.retriever:
                return self.pipeline.retriever.retrieve(query, k=k)
            elif strategy == "bm25" and self.pipeline.bm25_retriever:
                results = self.pipeline.bm25_retriever.retrieve(query, k=k)
                return [doc for doc, _ in results]
            elif strategy == "hybrid" and self.pipeline.hybrid_retriever:
                return self.pipeline.hybrid_retriever.retrieve(query, k=k)
            elif strategy == "hybrid_reranked" and self.pipeline.hybrid_retriever:
                docs = self.pipeline.hybrid_retriever.retrieve(query, k=k * 2)
                if self.pipeline.reranker and self.pipeline.reranker.is_ready:
                    docs = self.pipeline.reranker.rerank(query, docs, top_k=k)
                return docs[:k]
            return []
        except Exception as e:
            logger.warning(f"策略 {strategy} 检索失败: {e}")
            return []

    @staticmethod
    def _doc_ids(docs: list[Document]) -> list[str]:
        return [f"{d.metadata.get('source', 'unknown')}::{str(hash(d.page_content[:100]))}" for d in docs]

    @staticmethod
    def _get_relevant_ids(item: BenchmarkItem, retrieved_docs: list[Document]) -> set[str]:
        relevant = set()
        keywords = set(item.expected_answer_contains + item.relevant_doc_keywords)
        for doc in retrieved_docs:
            doc_id = f"{doc.metadata.get('source', 'unknown')}::{str(hash(doc.page_content[:100]))}"
            content = doc.page_content.lower()
            if any(kw.lower() in content for kw in keywords):
                relevant.add(doc_id)
        return relevant

    @staticmethod
    def _find_best(results: dict[str, dict[str, float]]) -> str:
        best_strategy, best_score = "unknown", -1.0
        for strategy, metrics in results.items():
            score = metrics.get("mrr", 0) * 0.4 + metrics.get("recall@3", 0) * 0.3 + metrics.get("ndcg@3", 0) * 0.3
            if score > best_score:
                best_score, best_strategy = score, strategy
        return best_strategy
