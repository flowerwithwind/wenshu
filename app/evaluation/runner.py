"""
评估运行器 - 包含新旧两套 API（向后兼容）
"""
from __future__ import annotations

import time
import uuid
from typing import Any

from langchain_core.documents import Document
from app.evaluation.benchmark import BenchmarkLoader, BenchmarkItem
from app.evaluation.metrics import MetricsCalculator
from app.evaluation.dataset import EVAL_DATASET, get_cases_by_category, EvalCase
from app.rag.pipeline import RAGPipeline
from app.nl2sql.translator import NL2SQLTranslator
from app.nl2sql.database import get_schema_info
from app.logger import get_logger

logger = get_logger(__name__)


# ==================== 旧 API（NL2SQL 评估运行器）====================

class EvalRunner:
    """NL2SQL 评测运行器"""

    def __init__(self, translator: NL2SQLTranslator | None = None, use_llm_judge: bool = True) -> None:
        self.translator = translator
        self.use_llm_judge = use_llm_judge
        self.llm_judge = None

    def run_all(self):
        from app.evaluation.metrics import EvalSummary, run_single_evaluation
        from app.evaluation.metrics import LLMJudge, evaluate_execution, exact_set_match
        if self.use_llm_judge:
            self.llm_judge = LLMJudge()
        schema = get_schema_info()
        results = []
        for case in EVAL_DATASET:
            try:
                sql = self.translator.translate(question=case.question, schema=schema) if self.translator else ""
            except Exception as e:
                sql = ""
            from app.evaluation.metrics import run_single_evaluation as rse
            results.append(rse(case.id, case.question, case.sql, sql, self.llm_judge))
        return EvalSummary(total=len(results), results=results)

    def run_category(self, category: str):
        cases = get_cases_by_category(category)
        schema = get_schema_info()
        from app.evaluation.metrics import EvalSummary, run_single_evaluation, LLMJudge
        if self.use_llm_judge:
            self.llm_judge = LLMJudge()
        results = []
        for case in cases:
            try:
                sql = self.translator.translate(question=case.question, schema=schema) if self.translator else ""
            except Exception as e:
                sql = ""
            results.append(run_single_evaluation(case.id, case.question, case.sql, sql, self.llm_judge))
        return EvalSummary(total=len(results), results=results)


def run_evaluation(category=None, translator=None, use_llm_judge=True):
    runner = EvalRunner(translator=translator, use_llm_judge=use_llm_judge)
    if category:
        return runner.run_category(category)
    return runner.run_all()


# ==================== 新 API（检索策略对比运行器）====================

class EvaluationRunner:
    """评估对比运行器（新 API：检索策略对比）"""

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
            results[strategy] = {k: round(v, 4) for k, v in self._run_strategy(strategy, items).items()}
        return {"eval_id": str(uuid.uuid4()), "total_items": len(items), "strategies": strategies, "results": results, "best_strategy": self._find_best(results), "created_at": time.strftime("%Y-%m-%dT%H:%M:%S")}

    def _run_strategy(self, strategy: str, items: list[BenchmarkItem]) -> dict[str, float]:
        all_m = {"recall@1": [], "recall@3": [], "recall@5": [], "precision@1": [], "precision@3": [], "precision@5": [], "mrr": [], "ndcg@1": [], "ndcg@3": [], "ndcg@5": []}
        for item in items:
            r = self._retrieve(strategy, item.question, k=5)
            ids = [f"{d.metadata.get('source','')}::{hash(d.page_content[:100])}" for d in r]
            rel = set()
            kw = set(item.expected_answer_contains + item.relevant_doc_keywords)
            for d in r:
                if any(k.lower() in d.page_content.lower() for k in kw):
                    rel.add(f"{d.metadata.get('source','')}::{hash(d.page_content[:100])}")
            ev = self.metrics.evaluate(ids, rel)
            for m, v in ev.items():
                if m in all_m:
                    all_m[m].append(v)
        return {m: round(sum(v)/len(v), 4) if v else 0.0 for m, v in all_m.items()}

    def _retrieve(self, strategy: str, query: str, k: int = 5) -> list[Document]:
        try:
            if strategy == "semantic" and self.pipeline.retriever:
                return self.pipeline.retriever.retrieve(query, k=k)
            elif strategy == "bm25" and self.pipeline.bm25_retriever:
                return [d for d, _ in self.pipeline.bm25_retriever.retrieve(query, k=k)]
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
    def _find_best(results: dict[str, dict[str, float]]) -> str:
        best, best_s = "unknown", -1.0
        for s, m in results.items():
            score = m.get("mrr", 0) * 0.4 + m.get("recall@3", 0) * 0.3 + m.get("ndcg@3", 0) * 0.3
            if score > best_s:
                best, best_s = s, score
        return best
