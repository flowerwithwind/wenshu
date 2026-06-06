"""
RAG Pipeline - 完整的检索增强生成流程
"""
import time
import uuid
from typing import List, Dict, Any, Optional, Generator
from app.config import DATASET_DIR
from app.rag.loader import DocumentLoader
from app.rag.splitter import DocumentSplitter
from app.rag.vectorstore import VectorStoreManager
from app.rag.retriever import SmartRetriever
from app.rag.generator import RAGGenerator
from app.models.schemas import SourceDocument


class RAGPipeline:
    """RAG 完整流程编排器"""

    def __init__(self):
        self.loader = DocumentLoader(DATASET_DIR)
        self.splitter = DocumentSplitter()
        self.vsm = VectorStoreManager()
        self.retriever = None
        self.generator = None
        self._init_components()

    def _init_components(self):
        """初始化各组件"""
        # 尝试加载已有向量存储
        if self.vsm.load():
            print(f"向量存储已加载，文档数: {self.vsm.get_collection_stats()['total']}")
        else:
            print("向量存储未初始化，请先执行数据预处理")

        self.retriever = SmartRetriever(self.vsm)

        try:
            self.generator = RAGGenerator()
        except ValueError as e:
            print(f"警告: {e}")
            self.generator = None

    def build_index(self) -> int:
        """构建/重建向量索引"""
        print("开始构建向量索引...")
        documents = self.loader.load_all()
        if not documents:
            print("未找到任何文档，请先添加数据到 data/datasets/ 目录")
            return 0

        chunks = self.splitter.split(documents)
        count = self.vsm.create_from_documents(chunks)
        print(f"向量索引构建完成，共 {count} 个文本块")
        return count

    def query(
        self, question: str, conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """执行 RAG 查询"""
        start_time = time.time()

        conv_id = conversation_id or str(uuid.uuid4())

        # 检索
        context, docs = self.retriever.retrieve_with_context(question)

        # 生成
        if self.generator:
            result = self.generator.generate(question, context, docs)
        else:
            result = {
                "answer": "模型服务未配置，请设置 DEEPSEEK_API_KEY 环境变量。",
                "chart_data": None,
            }

        elapsed_ms = (time.time() - start_time) * 1000

        sources = [
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
        context, docs = self.retriever.retrieve_with_context(question)

        if self.generator:
            yield from self.generator.generate_stream(question, context)
        else:
            yield "模型服务未配置，请设置 DEEPSEEK_API_KEY 环境变量。"

    def get_stats(self) -> Dict[str, Any]:
        """获取系统状态"""
        stats = self.vsm.get_collection_stats()
        return {
            "total_chunks": stats.get("total", 0),
            "model_ready": self.generator is not None,
            "vector_store_ready": self.vsm.is_ready(),
        }


# 全局单例
_pipeline: Optional[RAGPipeline] = None


def get_pipeline() -> RAGPipeline:
    """获取 RAG Pipeline 单例"""
    global _pipeline
    if _pipeline is None:
        _pipeline = RAGPipeline()
    return _pipeline