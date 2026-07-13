"""
文档加载器模块 - 支持多种格式的文档加载
"""
from __future__ import annotations

import os
from typing import Any
from langchain_core.documents import Document
from langchain_community.document_loaders import (
    TextLoader,
    CSVLoader,
    PyPDFLoader,
    UnstructuredExcelLoader,
    JSONLoader,
)
from app.logging import get_logger

logger = get_logger(__name__)


class DocumentLoader:
    """统一文档加载器，支持 txt, csv, pdf, xlsx, json 等格式"""

    SUPPORTED_EXTENSIONS: dict[str, str] = {
        ".txt": "text",
        ".csv": "csv",
        ".pdf": "pdf",
        ".xlsx": "excel",
        ".xls": "excel",
        ".json": "json",
    }

    def __init__(self, dataset_dir: str) -> None:
        self.dataset_dir: str = dataset_dir

    def load_all(self, exclude_csv: bool = False) -> list[Document]:
        """加载目录下所有支持的文档"""
        all_docs: list[Document] = []
        if not os.path.exists(self.dataset_dir):
            return all_docs

        for filename in os.listdir(self.dataset_dir):
            filepath: str = os.path.join(self.dataset_dir, filename)
            if not os.path.isfile(filepath):
                continue

            ext: str = os.path.splitext(filename)[1].lower()
            if exclude_csv and ext == ".csv":
                continue
            if ext in self.SUPPORTED_EXTENSIONS:
                try:
                    docs: list[Document] = self._load_single(filepath, ext)
                    for doc in docs:
                        doc.metadata["source"] = filename
                        doc.metadata["file_type"] = ext
                    all_docs.extend(docs)
                    logger.info(f"加载: {filename} ({len(docs)} 个文档块)")
                except Exception as e:
                    logger.error(f"加载失败: {filename} - {e}")

        return all_docs

    def _load_single(self, filepath: str, ext: str) -> list[Document]:
        """根据扩展名选择对应的加载器"""
        loaders: dict[str, Any] = {
            ".txt": lambda: TextLoader(filepath, encoding="utf-8").load(),
            ".csv": lambda: CSVLoader(
                filepath, encoding="utf-8",
                csv_args={"delimiter": ",", "quotechar": '"'}
            ).load(),
            ".pdf": lambda: PyPDFLoader(filepath).load(),
            ".xlsx": lambda: UnstructuredExcelLoader(
                filepath, mode="elements"
            ).load(),
            ".xls": lambda: UnstructuredExcelLoader(
                filepath, mode="elements"
            ).load(),
            ".json": lambda: JSONLoader(
                file_path=filepath,
                jq_schema=".[]",
                text_content=False,
            ).load(),
        }

        loader_fn = loaders.get(ext)
        if loader_fn:
            return loader_fn()
        return []

    def load_file(self, filepath: str) -> list[Document]:
        """加载单个文件"""
        ext: str = os.path.splitext(filepath)[1].lower()
        if ext in self.SUPPORTED_EXTENSIONS:
            docs: list[Document] = self._load_single(filepath, ext)
            for doc in docs:
                doc.metadata["source"] = os.path.basename(filepath)
            return docs
        return []
