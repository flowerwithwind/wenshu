from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any
from datetime import datetime


class SourceDocument(BaseModel):
    """来源文档"""
    content: str
    source: str = ""
    page: int | None = None
    score: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatRequest(BaseModel):
    """聊天请求"""
    question: str = Field(..., min_length=1, max_length=5000)
    conversation_id: str | None = None
    stream: bool = False


class SQLResult(BaseModel):
    """SQL 查询结果"""
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0


class ChatResponse(BaseModel):
    """聊天响应"""
    id: str
    question: str
    answer: str
    sources: list[SourceDocument] = Field(default_factory=list)
    conversation_id: str
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    response_time_ms: float = 0.0
    has_numeric_data: bool = False
    chart_data: dict[str, Any] | None = None
    sql: str | None = None
    sql_result: SQLResult | None = None


class DatasetInfo(BaseModel):
    """数据集信息"""
    name: str
    file_count: int
    total_chunks: int
    last_updated: str | None = None


class HistoryItem(BaseModel):
    """历史对话条目"""
    id: str
    question: str
    answer: str
    created_at: str


class ConversationList(BaseModel):
    """对话列表"""
    conversations: list[dict[str, Any]] = Field(default_factory=list)


class HealthResponse(BaseModel):
    """健康检查"""
    status: str
    version: str
    model: str
    vector_store: str


class ErrorResponse(BaseModel):
    """统一错误响应"""
    error_code: str
    message: str
    detail: str | None = None
