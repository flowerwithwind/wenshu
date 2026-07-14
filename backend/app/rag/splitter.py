"""
文本分割器模块 - 智能分割文档块
"""
from __future__ import annotations

from typing import Any
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.config import CHUNK_SIZE, CHUNK_OVERLAP
from app.logger import get_logger

logger = get_logger(__name__)


class DocumentSplitter:
    """文档分割器，支持中文友好的文本分割"""

    def __init__(
        self,
        chunk_size: int = CHUNK_SIZE,
        chunk_overlap: int = CHUNK_OVERLAP,
    ) -> None:
        self.chunk_size: int = chunk_size
        self.chunk_overlap: int = chunk_overlap
        self.text_splitter: RecursiveCharacterTextSplitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""],
        )

    def split(self, documents: list[Document]) -> list[Document]:
        """分割文档列表"""
        if not documents:
            return []
        chunks: list[Document] = self.text_splitter.split_documents(documents)
        for i, chunk in enumerate(chunks):
            chunk.metadata["chunk_id"] = i
        logger.info(f"文档分割完成: {len(documents)} -> {len(chunks)} 个文本块")
        return chunks

    def split_text(self, text: str, metadata: dict[str, Any] | None = None) -> list[Document]:
        """分割单段文本"""
        chunks: list[Document] = self.text_splitter.create_documents(
            texts=[text],
            metadatas=[metadata or {}],
        )
        return chunks
