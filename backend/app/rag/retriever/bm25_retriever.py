"""
BM25 关键词召回模块

基于 rank_bm25 实现，适用于精确术语匹配场景。
与语义检索互补：语义擅长同义泛化，BM25 擅长精确关键词命中。

用法:
    bm25 = BM25Retriever()
    bm25.fit(documents)
    results = bm25.retrieve("上个月销量", k=4)
"""
from __future__ import annotations

import time
from typing import Any

from langchain_core.documents import Document
from app.logger import get_logger

logger = get_logger(__name__)


class BM25Retriever:
    """BM25 关键词检索器"""

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        """
        Args:
            k1: BM25 饱和控制参数（1.2~2.0），越高则词频影响越大
            b: 文档长度归一化参数（0~1），0 表示不归一化
        """
        self.k1: float = k1
        self.b: float = b
        self._bm25: Any = None
        self._documents: list[Document] = []
        self._is_fitted: bool = False

    @property
    def is_fitted(self) -> bool:
        """是否已构建索引"""
        return self._is_fitted

    def fit(self, documents: list[Document]) -> None:
        """
        构建 BM25 索引

        Args:
            documents: 待索引的文档列表
        """
        from rank_bm25 import BM25Okapi

        self._documents = documents
        if not documents:
            logger.warning("BM25: 空文档列表，跳过索引构建")
            self._is_fitted = False
            return

        tokenized = [self._tokenize(doc.page_content) for doc in documents]
        self._bm25 = BM25Okapi(tokenized, k1=self.k1, b=self.b)
        self._is_fitted = True
        logger.info(f"BM25 索引构建完成: {len(documents)} 篇文档")

    def retrieve(
        self, query: str, k: int = 4
    ) -> list[tuple[Document, float]]:
        """
        检索 Top-K 相关文档

        Args:
            query: 查询文本
            k: 返回数量

        Returns:
            [(Document, score), ...]，score 为 BM25 原始分数
        """
        if not self._is_fitted or self._bm25 is None:
            return []

        start = time.time()
        tokenized_query = self._tokenize(query)
        scores = self._bm25.get_scores(tokenized_query)

        # 按分数降序取 Top-K
        top_indices = sorted(
            range(len(scores)), key=lambda i: scores[i], reverse=True
        )[:k]

        results: list[tuple[Document, float]] = []
        for idx in top_indices:
            if scores[idx] > 0:
                doc = self._documents[idx]
                doc.metadata["bm25_score"] = round(scores[idx], 4)
                results.append((doc, scores[idx]))

        elapsed = (time.time() - start) * 1000
        logger.debug(f"BM25 检索完成: query={query[:30]}, hits={len(results)}, {elapsed:.0f}ms")
        return results

    def retrieve_with_context(
        self, query: str, k: int = 4
    ) -> tuple[str, list[Document]]:
        """检索并返回格式化的上下文"""
        docs_with_scores = self.retrieve(query, k=k)
        docs = [doc for doc, _ in docs_with_scores]
        if not docs:
            return "", []

        context_parts = []
        for i, doc in enumerate(docs):
            source = doc.metadata.get("source", "未知")
            score = doc.metadata.get("bm25_score", 0)
            context_parts.append(f"[BM25来源 {i+1}: {source} (score={score})]\n{doc.page_content}")

        context = "\n\n---\n\n".join(context_parts)
        return context, docs

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """
        中文分词：按空白符 + 标点分割
        对于中文，简单的字符级 unigram 即可达到不错效果
        """
        import re
        # 统一小写，保留中文、英文、数字
        text = text.lower()
        # 将非字母数字中文的字符替换为空格
        text = re.sub(r'[^a-z0-9\u4e00-\u9fff]', ' ', text)
        # 分词：英文按空格，中文按单字
        tokens: list[str] = []
        for part in text.split():
            if part and '\u4e00' <= part[0] <= '\u9fff':
                # 中文部分按单字切分
                tokens.extend(list(part))
            else:
                tokens.append(part)
        return tokens
