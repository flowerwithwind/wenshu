"""意图识别器 — 将用户问题分流到不同处理管线"""
from __future__ import annotations

from enum import Enum


class Intent(str, Enum):
    DATA_QUERY = "DATA_QUERY"            # 数据查询 → NL2SQL
    DATA_ANALYSIS = "DATA_ANALYSIS"      # 数据分析/洞察 → NL2SQL + 增强回答
    KNOWLEDGE_QA = "KNOWLEDGE_QA"        # 知识问答 → RAG
    CHITCHAT = "CHITCHAT"                # 闲聊 → 直接回复
    META = "META"                        # 系统元问题 → 直接回复


class IntentClassifier:
    """基于规则的意图分类器（快速、零延迟），复杂场景可升级为 LLM 分类"""

    # 闲聊关键词
    CHITCHAT_KEYWORDS: list[str] = ["你好", "谢谢", "再见", "你是谁", "你能做什么", "介绍一下", "hello", "hi"]
    # 元问题关键词
    META_KEYWORDS: list[str] = ["有哪些表", "表结构", "数据来源", "怎么用", "有哪些数据"]
    # 知识问答关键词
    KNOWLEDGE_KEYWORDS: list[str] = ["什么是", "定义", "概念", "原理", "为什么", "怎么计算", "解释"]
    # 数据分析关键词（触发增强回答：洞察+建议）
    ANALYSIS_KEYWORDS: list[str] = ["趋势", "预测", "建议", "优化", "原因分析", "为什么下降", "为什么增长", "异常"]

    @classmethod
    def classify(cls, question: str) -> Intent:
        q_lower: str = question.lower().strip()
        # 1. 闲聊检查
        for kw in cls.CHITCHAT_KEYWORDS:
            if kw in q_lower:
                return Intent.CHITCHAT
        # 2. 元问题检查
        for kw in cls.META_KEYWORDS:
            if kw in q_lower:
                return Intent.META
        # 3. 知识问答检查
        for kw in cls.KNOWLEDGE_KEYWORDS:
            if kw in q_lower:
                return Intent.KNOWLEDGE_QA
        # 4. 数据分析检查
        for kw in cls.ANALYSIS_KEYWORDS:
            if kw in q_lower:
                return Intent.DATA_ANALYSIS
        # 5. 默认数据查询
        return Intent.DATA_QUERY
