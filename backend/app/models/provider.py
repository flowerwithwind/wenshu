"""
多模型适配器 — 支持 DeepSeek / OpenAI GPT / Anthropic Claude 无缝切换

用法:
    from app.models.provider import get_chat_model, LLMConfig
    llm = get_chat_model(temperature=0.1, max_tokens=1024)
    response = llm.invoke([...])
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.config import (
    LLM_PROVIDER,
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL,
    OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL,
    ANTHROPIC_API_KEY, ANTHROPIC_MODEL,
)


class ModelProvider(ABC):
    """模型供应商抽象基类"""

    @abstractmethod
    def get_chat_model(self, temperature: float = 0.1, max_tokens: int = 1024) -> BaseChatModel:
        ...


class DeepSeekProvider(ModelProvider):
    """DeepSeek (OpenAI 兼容 API)"""

    def get_chat_model(self, temperature: float = 0.1, max_tokens: int = 1024) -> BaseChatModel:
        return ChatOpenAI(
            model=DEEPSEEK_MODEL,
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
            temperature=temperature,
            max_tokens=max_tokens,
        )


class OpenAIProvider(ModelProvider):
    """OpenAI GPT-4o / GPT-4o-mini"""

    def get_chat_model(self, temperature: float = 0.1, max_tokens: int = 1024) -> BaseChatModel:
        return ChatOpenAI(
            model=OPENAI_MODEL,
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL or "https://api.openai.com/v1",
            temperature=temperature,
            max_tokens=max_tokens,
        )


class AnthropicProvider(ModelProvider):
    """Anthropic Claude"""

    def get_chat_model(self, temperature: float = 0.1, max_tokens: int = 1024) -> BaseChatModel:
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError:
            raise ImportError("使用 Claude 需要安装 langchain-anthropic: pip install langchain-anthropic")
        return ChatAnthropic(
            model=ANTHROPIC_MODEL,
            api_key=ANTHROPIC_API_KEY,
            temperature=temperature,
            max_tokens=max_tokens,
        )


# 供应商注册表
_PROVIDERS: dict[str, type[ModelProvider]] = {
    "deepseek": DeepSeekProvider,
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
}


def get_model_provider(provider_name: str | None = None) -> ModelProvider:
    """获取模型供应商实例"""
    name = (provider_name or LLM_PROVIDER).lower()
    provider_cls = _PROVIDERS.get(name)
    if not provider_cls:
        available = ", ".join(_PROVIDERS)
        raise ValueError(f"不支持的模型供应商: '{name}'，可选: {available}")
    return provider_cls()


def get_chat_model(temperature: float = 0.1, max_tokens: int = 1024,
                   provider_name: str | None = None) -> BaseChatModel:
    """快捷方式：直接获取 ChatModel"""
    provider = get_model_provider(provider_name)
    return provider.get_chat_model(temperature=temperature, max_tokens=max_tokens)


# 供应商元数据（前端展示用）
PROVIDER_META: dict[str, dict[str, str]] = {
    "deepseek": {
        "label": "DeepSeek",
        "model": DEEPSEEK_MODEL,
        "description": "DeepSeek-V4 / DeepSeek-Chat",
    },
    "openai": {
        "label": "OpenAI",
        "model": OPENAI_MODEL,
        "description": "GPT-4o / GPT-4o-mini",
    },
    "anthropic": {
        "label": "Anthropic",
        "model": ANTHROPIC_MODEL,
        "description": "Claude 3.5 Sonnet / Claude 4",
    },
}


def list_providers() -> list[dict[str, str]]:
    """列出所有可用供应商（用于前端切换）"""
    return [
        {"key": k, **v}
        for k, v in PROVIDER_META.items()
        if k == "deepseek" or _has_api_key(k)
    ]


def _has_api_key(provider: str) -> bool:
    """检查供应商的 API Key 是否已配置"""
    key_map = {
        "deepseek": DEEPSEEK_API_KEY,
        "openai": OPENAI_API_KEY,
        "anthropic": ANTHROPIC_API_KEY,
    }
    return bool(key_map.get(provider))
