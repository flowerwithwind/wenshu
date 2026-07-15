"""
Cross-encoder 精排模块

对召回结果（Bi-encoder 初筛）做精细重排序，提升 Top-K 准确率。

设计原则:
- Bi-encoder（双编码器）：适合大规模初筛，query/doc 独立编码
- Cross-encoder（交叉编码器）：适合小规模精排，query/doc 交互编码，精度高但慢

使用策略:
    retrieve → top-K (Bi-encoder) → rerank (Cross-encoder) → top-N (精排后)

降级策略:
    Cross-encoder 模型加载失败 → 跳过精排，直接返回召回结果
"""
from __future__ import annotations

import time
from typing import Any

from langchain_core.documents import Document
from app.logger import get_logger
from app.config import RERANKER_MODEL, RERANKER_DEVICE

logger = get_logger(__name__)


class CrossEncoderReranker:
    """Cross-encoder 精排器"""

    def __init__(
        self,
        model_name: str = RERANKER_MODEL,
        device: str = RERANKER_DEVICE,
    ) -> None:
        """
        Args:
            model_name: Cross-encoder 模型名
            device: 运行设备 (cpu / cuda)
        """
        self.model_name: str = model_name
        self.device: str = device
        self._model: Any = None
        self._is_ready: bool = False
        self._init_model()

    @property
    def is_ready(self) -> bool:
        return self._is_ready

    def _init_model(self) -> None:
        """初始化 Cross-encoder 模型（惰性加载，失败时降级）"""
        try:
            from sentence_transformers import CrossEncoder

            logger.info(f"正在加载 Cross-encoder: {self.model_name} ...")
            self._model = CrossEncoder(
                self.model_name,
                device=self.device,
                trust_remote_code=True,
            )
            self._is_ready = True
            logger.info("Cross-encoder 加载完成")
        except Exception as e:
            logger.warning(
                f"Cross-encoder 加载失败 ({e})，已降级跳过精排。"
                f"如需使用，请安装: pip install sentence-transformers"
            )
            self._model = None
            self._is_ready = False

    def rerank(
        self,
        query: str,
        documents: list[Document],
        top_k: int = 4,
    ) -> list[Document]:
        """
    对候选文档执行 Cross-encoder 精排

        Args:
            query: 原始查询
            documents: 候选文档列表（通常来自 Bi-encoder 初筛）
            top_k: 最终返回数量

        Returns:
            精排后的 Document 列表
        """
        if not self._is_ready or self._model is None:
            logger.debug("Cross-encoder 未就绪，跳过精排")
            return documents[:top_k]

        if not documents:
            return []

        start = time.time()

        # 构建 (query, doc) 对
        pairs = [(query, doc.page_content) for doc in documents]

        # 推理得分
        try:
            scores = self._model.predict(pairs)
        except Exception as e:
            logger.warning(f"Cross-encoder 推理失败: {e}，返回原始排序")
            return documents[:top_k]

        # 按得分降序排列
        scored = list(zip(documents, scores))
        scored.sort(key=lambda x: x[1], reverse=True)

        # 写入精排分数
        for doc, score in scored:
            doc.metadata["rerank_score"] = round(float(score), 4)

        elapsed = (time.time() - start) * 1000
        logger.debug(
            f"Cross-encoder 精排: {len(documents)} 篇 → {top_k} 篇, {elapsed:.0f}ms"
        )

        return [doc for doc, _ in scored[:top_k]]

    def rerank_with_scores(
        self,
        query: str,
        documents: list[Document],
        top_k: int = 4,
    ) -> list[tuple[Document, float]]:
        """精排并返回分数"""
        reranked = self.rerank(query, documents, top_k)
        return [(doc, doc.metadata.get("rerank_score", 0)) for doc in reranked]
