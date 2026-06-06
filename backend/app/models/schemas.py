from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class SourceDocument(BaseModel):
    """来源文档"""
    content: str
    source: str = ""
    page: Optional[int] = None
    score: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChatRequest(BaseModel):
    """聊天请求"""
    question: str = Field(..., min_length=1, max_length=5000)
    conversation_id: Optional[str] = None
    stream: bool = False


class ChatResponse(BaseModel):
    """聊天响应"""
    id: str
    question: str
    answer: str
    sources: List[SourceDocument] = Field(default_factory=list)
    conversation_id: str
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    response_time_ms: float = 0.0
    has_numeric_data: bool = False
    chart_data: Optional[Dict[str, Any]] = None


class DatasetInfo(BaseModel):
    """数据集信息"""
    name: str
    file_count: int
    total_chunks: int
    last_updated: Optional[str] = None


class HistoryItem(BaseModel):
    """历史对话条目"""
    id: str
    question: str
    answer: str
    created_at: str


class ConversationList(BaseModel):
    """对话列表"""
    conversations: List[Dict[str, Any]] = Field(default_factory=list)


class HealthResponse(BaseModel):
    """健康检查"""
    status: str
    version: str
    model: str
    vector_store: str