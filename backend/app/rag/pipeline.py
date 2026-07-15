"""
RAG Pipeline - 完整的检索增强生成流程（增强版：支持多路召回 + 精排）
"""
from __future__ import annotations

import time
import uuid
import json
import os
from typing import Any, Generator
from langchain_core.documents import Document
from app.config import DATASET_DIR, RETRIEVER_MODE, HYBRID_ALPHA
from app.rag.loader import DocumentLoader
from app.rag.splitter import DocumentSplitter
from app.rag.vectorstore import VectorStoreManager
from app.rag.retriever import SmartRetriever
from app.rag.retriever.bm25_retriever import BM25Retriever
from app.rag.retriever.hybrid_retriever import HybridRetriever
from app.rag.retriever.reranker import CrossEncoderReranker
from app.rag.generator import RAGGenerator
from app.models.schemas import SourceDocument
from app.logger import get_logger

logger = get_logger(__name__)


class RAGPipeline:
    """RAG 完整流程编排器（支持语义/BM25/混合检索 + Cross-encoder 精排）"""

    def __init__(self) -> None:
        self.loader: DocumentLoader = DocumentLoader(DATASET_DIR)
        self.splitter: DocumentSplitter = DocumentSplitter()
        self.vsm: VectorStoreManager = VectorStoreManager()
        self.retriever: SmartRetriever | None = None
        self.bm25_retriever: BM25Retriever | None = None
        self.hybrid_retriever: HybridRetriever | None = None
        self.reranker: CrossEncoderReranker | None = None
        self.generator: RAGGenerator | None = None
        self._init_components()

    def _init_components(self) -> None:
        """初始化各组件"""
        # 尝试加载已有向量存储；损坏时标记未就绪，不中断启动
        try:
            if self.vsm.load():
                stats = self.vsm.get_collection_stats()
                logger.info(f"向量存储已加载，文档数: {stats.get('total', 0)}")
            else:
                logger.warning(
                    "向量存储未初始化或索引损坏，NL2SQL 仍可用；"
                    "可调用 POST /api/rebuild-index 或运行 python scripts/preprocess.py 重建"
                )
        except Exception as e:
            logger.warning(f"向量存储加载异常（已降级继续启动）: {e}")
            self.vsm.vector_store = None

        self.retriever = SmartRetriever(self.vsm)

        # 初始化 BM25 检索器（仅当向量就绪且有文档时）
        self.bm25_retriever = BM25Retriever()
        if self.vsm.is_ready():
            try:
                all_docs = self.vsm.vector_store.get()
                if all_docs and all_docs.get("documents"):
                    from langchain_core.documents import Document as LCDocument
                    docs_for_bm25 = [
                        LCDocument(page_content=doc) for doc in all_docs["documents"]
                    ]
                    self.bm25_retriever.fit(docs_for_bm25)
                    logger.info(f"BM25 索引已构建: {len(docs_for_bm25)} 篇文档")
            except Exception as e:
                logger.warning(f"BM25 索引构建失败（已降级）: {e}")

        # 初始化混合检索器
        if self.bm25_retriever.is_fitted:
            self.hybrid_retriever = HybridRetriever(
                semantic_retriever=self.retriever,
                bm25_retriever=self.bm25_retriever,
                alpha=HYBRID_ALPHA,
            )
            logger.info(f"混合检索器就绪 (alpha={HYBRID_ALPHA})")

        # 初始化 Cross-encoder 精排
        self.reranker = CrossEncoderReranker()

        try:
            self.generator = RAGGenerator()
        except ValueError as e:
            logger.warning(f"警告: {e}")
            self.generator = None

    def build_index(self) -> int:
        """构建/重建向量索引 - 使用 NL2SQL 知识库（示例、表结构、映射、同义词）"""
        logger.info("开始构建向量索引...")

        documents: list[Document] = []

        # 1. 加载非 CSV 文档（如 txt 说明文件）
        txt_docs: list[Document] = self.loader.load_all(exclude_csv=True)
        documents.extend(txt_docs)
        logger.info(f"加载了 {len(txt_docs)} 个非 CSV 文档")

        # 2. 加载 NL2SQL 知识库 JSON
        knowledge_path: str = os.path.join(DATASET_DIR, "nl2sql_knowledge.json")
        if os.path.exists(knowledge_path):
            with open(knowledge_path, "r", encoding="utf-8") as f:
                knowledge: dict[str, Any] = json.load(f)

            # 2a. Question-SQL 示例对（P0 - 最重要）
            examples: list[dict[str, Any]] = knowledge.get("question_sql_examples", [])
            for ex in examples:
                content: str = (
                    f"【示例问题】{ex['question']}\n"
                    f"【对应SQL】{ex['sql']}\n"
                    f"【涉及表】{', '.join(ex.get('tables', []))}\n"
                    f"【标签】{', '.join(ex.get('tags', []))}"
                )
                doc: Document = Document(
                    page_content=content,
                    metadata={
                        "source": "nl2sql_knowledge.json",
                        "type": "question_sql_example",
                        "tables": ex.get("tables", []),
                        "tags": ex.get("tags", []),
                    }
                )
                documents.append(doc)
            logger.info(f"Question-SQL 示例: {len(examples)} 条")

            # 2b. 增强表结构 + 列语义（P1）
            schemas: list[dict[str, Any]] = knowledge.get("table_schemas", [])
            for schema in schemas:
                col_lines: list[str] = []
                for col in schema.get("columns", []):
                    col_lines.append(
                        f"  - {col['name']}({col['type']}): {col['description']}, "
                        f"取值范围: {col.get('range', 'N/A')}"
                    )
                content = (
                    f"【数据表】{schema['table']}\n"
                    f"【描述】{schema['description']}\n"
                    f"【列信息】\n" + "\n".join(col_lines) + "\n"
                    f"【典型问题】\n" + "\n".join(f"  - {q}" for q in schema.get("typical_questions", []))
                )
                doc = Document(
                    page_content=content,
                    metadata={
                        "source": "nl2sql_knowledge.json",
                        "type": "table_schema",
                        "table": schema["table"],
                    }
                )
                documents.append(doc)
            logger.info(f"增强表结构: {len(schemas)} 个表")

            # 2c. 领域值映射（P2）
            mappings: list[dict[str, Any]] = knowledge.get("domain_mappings", [])
            for m in mappings:
                content = (
                    f"【领域术语】{m['term']}\n"
                    f"【SQL映射】{m['mapping']}\n"
                    f"【适用表】{m['applicable_table']}\n"
                    f'当用户提到「{m["term"]}」时，应转换为SQL条件: {m["mapping"]}'
                )
                doc = Document(
                    page_content=content,
                    metadata={
                        "source": "nl2sql_knowledge.json",
                        "type": "domain_mapping",
                        "term": m["term"],
                        "table": m["applicable_table"],
                    }
                )
                documents.append(doc)
            logger.info(f"领域值映射: {len(mappings)} 条")

            # 2d. 同义词映射（P3）
            synonyms: list[dict[str, Any]] = knowledge.get("synonym_mappings", [])
            for s in synonyms:
                content = (
                    f"【同义词组】{', '.join(s['synonyms'])}\n"
                    f"【对应列】{s['target_column']}\n"
                    f"【所属表】{s['table']}\n"
                    f"用户提到以下任何词时，应映射到列 [{s['target_column']}]: {', '.join(s['synonyms'])}"
                )
                doc = Document(
                    page_content=content,
                    metadata={
                        "source": "nl2sql_knowledge.json",
                        "type": "synonym_mapping",
                        "table": s["table"],
                        "target_column": s["target_column"],
                    }
                )
                documents.append(doc)
            logger.info(f"同义词映射: {len(synonyms)} 条")
        else:
            logger.warning("nl2sql_knowledge.json 未找到，跳过知识库加载")

        logger.info(f"共 {len(documents)} 个文档")

        if not documents:
            logger.warning("未找到任何文档，请先添加数据到 data/datasets/ 目录")
            return 0

        chunks: list[Document] = self.splitter.split(documents)
        count: int = self.vsm.create_from_documents(chunks)
        logger.info(f"向量索引构建完成，共 {count} 个文本块")

        # 重建 BM25 索引
        if count > 0 and self.bm25_retriever is not None:
            self.bm25_retriever.fit(chunks)
            # 重建混合检索器
            if self.bm25_retriever.is_fitted:
                self.hybrid_retriever = HybridRetriever(
                    semantic_retriever=self.retriever,
                    bm25_retriever=self.bm25_retriever,
                    alpha=HYBRID_ALPHA,
                )
                logger.info(f"BM25/混合检索索引重建完成: {count} 个文本块")
        return count

    def hybrid_retrieve(
        self, query: str, k: int = 4
    ) -> tuple[str, list[Document]]:
        """
        混合检索入口（根据 RETRIEVER_MODE 自动选择检索策略）

        Args:
            query: 查询文本
            k: 返回数量

        Returns:
            (context_str, documents)

        策略:
            - hybrid: 语义+BM25混合检索 → Cross-encoder精排
            - bm25: 纯BM25检索
            - semantic: 纯语义检索（与原有行为一致）
        """
        mode = RETRIEVER_MODE.lower()

        if mode == "hybrid" and self.hybrid_retriever is not None:
            docs = self.hybrid_retriever.retrieve(query, k=k * 2)
            # Cross-encoder 精排
            if self.reranker is not None and self.reranker.is_ready:
                docs = self.reranker.rerank(query, docs, top_k=k)
            # 格式化上下文
            return self._format_retrieved_docs(docs), docs

        elif mode == "bm25" and self.bm25_retriever is not None:
            context, docs = self.bm25_retriever.retrieve_with_context(query, k=k)
            return context, docs

        # 默认：纯语义检索（向后兼容）
        context, docs = self.retriever.retrieve_with_context(query)
        return context, docs if docs else "", []

    @staticmethod
    def _format_retrieved_docs(docs: list[Document]) -> str:
        """格式化检索结果文档为上下文字符串"""
        if not docs:
            return ""
        context_parts = []
        for i, doc in enumerate(docs):
            source = doc.metadata.get("source", "未知")
            score = doc.metadata.get("hybrid_score") or doc.metadata.get("score", 0)
            context_parts.append(f"[来源 {i+1}: {source} (score={score})]\n{doc.page_content}")
        return "\n\n---\n\n".join(context_parts)

    def query(
        self, question: str, conversation_id: str | None = None
    ) -> dict[str, Any]:
        """执行 RAG 查询"""
        start_time: float = time.time()

        conv_id: str = conversation_id or str(uuid.uuid4())

        # 检索（使用混合检索，支持语义/BM25/混合策略）
        context, docs = self.hybrid_retrieve(question)

        # 生成
        if self.generator:
            result: dict[str, Any] = self.generator.generate(question, context, docs)
        else:
            result = {
                "answer": "模型服务未配置，请设置 DEEPSEEK_API_KEY 环境变量。",
                "chart_data": None,
            }

        elapsed_ms: float = (time.time() - start_time) * 1000

        sources: list[SourceDocument] = [
            SourceDocument(
                content=doc.page_content[:200],
                source=doc.metadata.get("source", ""),
                score=doc.metadata.get("score"),
                metadata=doc.metadata,
            )
            for doc in docs
        ]

        return {
            "id": str(uuid.uuid4()),
            "question": question,
            "answer": result["answer"],
            "sources": sources,
            "conversation_id": conv_id,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "response_time_ms": round(elapsed_ms, 2),
            "has_numeric_data": result.get("chart_data") is not None,
            "chart_data": result.get("chart_data"),
        }

    def query_stream(
        self, question: str
    ) -> Generator[str, None, None]:
        """流式 RAG 查询"""
        context, docs = self.hybrid_retrieve(question)

        if self.generator:
            yield from self.generator.generate_stream(question, context)
        else:
            yield "模型服务未配置，请设置 DEEPSEEK_API_KEY 环境变量。"

    def get_stats(self) -> dict[str, Any]:
        """获取系统状态"""
        stats: dict[str, int] = self.vsm.get_collection_stats()
        return {
            "total_chunks": stats.get("total", 0),
            "model_ready": self.generator is not None,
            "vector_store_ready": self.vsm.is_ready(),
        }


# 全局单例
_pipeline: RAGPipeline | None = None


def get_pipeline() -> RAGPipeline:
    """获取 RAG Pipeline 单例"""
    global _pipeline
    if _pipeline is None:
        _pipeline = RAGPipeline()
    return _pipeline
