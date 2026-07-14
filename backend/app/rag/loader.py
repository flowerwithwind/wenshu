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
)
from app.logger import get_logger

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
            # 知识库 JSON 由 pipeline 专用逻辑解析，避免 JSONLoader 依赖 jq 失败
            if filename == "nl2sql_knowledge.json":
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
        if ext == ".txt":
            return TextLoader(filepath, encoding="utf-8").load()
        if ext == ".csv":
            return CSVLoader(
                filepath, encoding="utf-8",
                csv_args={"delimiter": ",", "quotechar": '"'},
            ).load()
        if ext == ".pdf":
            return PyPDFLoader(filepath).load()
        if ext in (".xlsx", ".xls"):
            return UnstructuredExcelLoader(filepath, mode="elements").load()
        if ext == ".json":
            return self._load_json_without_jq(filepath)
        return []

    def _load_json_without_jq(self, filepath: str) -> list[Document]:
        """不依赖 jq 的 JSON 加载（数组/对象转文本块）"""
        import json

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        docs: list[Document] = []
        if isinstance(data, list):
            for i, item in enumerate(data):
                docs.append(Document(
                    page_content=json.dumps(item, ensure_ascii=False, indent=2)
                    if not isinstance(item, str) else item,
                    metadata={"index": i},
                ))
        elif isinstance(data, dict):
            docs.append(Document(
                page_content=json.dumps(data, ensure_ascii=False, indent=2),
                metadata={},
            ))
        else:
            docs.append(Document(page_content=str(data), metadata={}))
        return docs

    def load_file(self, filepath: str) -> list[Document]:
        """加载单个文件"""
        ext: str = os.path.splitext(filepath)[1].lower()
        if ext in self.SUPPORTED_EXTENSIONS:
            docs: list[Document] = self._load_single(filepath, ext)
            for doc in docs:
                doc.metadata["source"] = os.path.basename(filepath)
            return docs
        return []
