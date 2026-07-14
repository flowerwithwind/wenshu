"""
多模型适配器 — DeepSeek / OpenAI / Anthropic
配置优先读取运行时 llm_settings.json（前端可改），其次 .env
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.config import LLM_PROVIDER
from app.services.llm_settings import (
    get_settings,
    get_provider_config,
    get_active_provider,
    save_settings,
    public_settings,
    load_settings,
)


class ModelProvider(ABC):
    @abstractmethod
    def get_chat_model(self, temperature: float = 0.1, max_tokens: int = 1024) -> BaseChatModel:
        ...


class DeepSeekProvider(ModelProvider):
    def get_chat_model(self, temperature: float = 0.1, max_tokens: int = 1024) -> BaseChatModel:
        cfg = get_provider_config("deepseek")
        api_key = cfg.get("api_key") or ""
        if not api_key:
            raise ValueError("DeepSeek API Key 未配置，请在「模型配置」中填写")
        return ChatOpenAI(
            model=cfg.get("model") or "deepseek-chat",
            api_key=api_key,
            base_url=cfg.get("base_url") or "https://api.deepseek.com/v1",
            temperature=temperature,
            max_tokens=max_tokens,
        )


class OpenAIProvider(ModelProvider):
    def get_chat_model(self, temperature: float = 0.1, max_tokens: int = 1024) -> BaseChatModel:
        cfg = get_provider_config("openai")
        api_key = cfg.get("api_key") or ""
        if not api_key:
            raise ValueError("OpenAI API Key 未配置，请在「模型配置」中填写")
        return ChatOpenAI(
            model=cfg.get("model") or "gpt-4o",
            api_key=api_key,
            base_url=cfg.get("base_url") or "https://api.openai.com/v1",
            temperature=temperature,
            max_tokens=max_tokens,
        )


class AnthropicProvider(ModelProvider):
    def get_chat_model(self, temperature: float = 0.1, max_tokens: int = 1024) -> BaseChatModel:
        cfg = get_provider_config("anthropic")
        api_key = cfg.get("api_key") or ""
        if not api_key:
            raise ValueError("Anthropic API Key 未配置，请在「模型配置」中填写")
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as e:
            raise ImportError(
                "使用 Claude 需要安装 langchain-anthropic: pip install langchain-anthropic"
            ) from e
        return ChatAnthropic(
            model=cfg.get("model") or "claude-sonnet-4-20250514",
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
        )


_PROVIDERS: dict[str, type[ModelProvider]] = {
    "deepseek": DeepSeekProvider,
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
}

PROVIDER_META: dict[str, dict[str, str]] = {
    "deepseek": {
        "label": "DeepSeek",
        "description": "DeepSeek Chat（默认推荐）",
        "default_base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
    },
    "openai": {
        "label": "OpenAI",
        "description": "GPT-4o / GPT-4o-mini",
        "default_base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o",
    },
    "anthropic": {
        "label": "Anthropic",
        "description": "Claude Sonnet",
        "default_base_url": "",
        "default_model": "claude-sonnet-4-20250514",
    },
}


def get_current_provider_name() -> str:
    try:
        return get_active_provider()
    except Exception:
        return (LLM_PROVIDER or "deepseek").lower()


def get_model_provider(provider_name: str | None = None) -> ModelProvider:
    name = (provider_name or get_current_provider_name() or "deepseek").lower()
    provider_cls = _PROVIDERS.get(name)
    if not provider_cls:
        raise ValueError(f"不支持的模型供应商: '{name}'，可选: {', '.join(_PROVIDERS)}")
    return provider_cls()


def get_chat_model(
    temperature: float = 0.1,
    max_tokens: int = 1024,
    provider_name: str | None = None,
) -> BaseChatModel:
    return get_model_provider(provider_name).get_chat_model(temperature, max_tokens)


def _has_api_key(provider: str) -> bool:
    cfg = get_provider_config(provider)
    return bool(cfg.get("api_key"))


def list_providers() -> list[dict[str, Any]]:
    s = get_settings()
    current = s.get("provider", "deepseek")
    result: list[dict[str, Any]] = []
    for k, meta in PROVIDER_META.items():
        cfg = s.get(k) or {}
        configured = bool(cfg.get("api_key"))
        result.append({
            "key": k,
            "label": meta["label"],
            "model": cfg.get("model") or meta["default_model"],
            "description": meta["description"],
            "base_url": cfg.get("base_url") or meta.get("default_base_url", ""),
            "configured": configured,
            "available": configured,
            "current": k == current,
        })
    return result


def get_provider_status() -> dict[str, Any]:
    s = get_settings()
    current = s.get("provider", "deepseek")
    meta = PROVIDER_META.get(current, PROVIDER_META["deepseek"])
    cfg = s.get(current) or {}
    return {
        "provider": current,
        "label": meta["label"],
        "model": cfg.get("model") or meta["default_model"],
        "description": meta["description"],
        "configured": bool(cfg.get("api_key")),
        "providers": list_providers(),
        "settings": public_settings(),
    }


def invalidate_llm_caches() -> None:
    try:
        import app.nl2sql.pipeline as nl2sql_mod
        nl2sql_mod._pipeline = None
    except Exception:
        pass
    try:
        import app.agent.agent as agent_mod
        agent_mod._agent = None
    except Exception:
        pass
    try:
        import app.rag.pipeline as rag_mod
        if rag_mod._pipeline is not None:
            rag_mod._pipeline.generator = None
    except Exception:
        pass


def set_current_provider(provider_name: str) -> dict[str, Any]:
    name = (provider_name or "").lower().strip()
    if name not in _PROVIDERS:
        raise ValueError(f"不支持的供应商: {provider_name}")
    if not _has_api_key(name):
        raise ValueError(f"供应商「{PROVIDER_META[name]['label']}」尚未配置 API Key，请先在模型配置中填写")
    save_settings({"provider": name})
    invalidate_llm_caches()
    return get_provider_status()


def update_llm_config(payload: dict[str, Any]) -> dict[str, Any]:
    """从前端保存完整模型配置并可选切换当前供应商"""
    save_settings(payload)
    # 若指定了 provider 且有 key，确保可用
    s = get_settings()
    name = s.get("provider", "deepseek")
    if not _has_api_key(name):
        # 尝试自动选一个有 key 的
        for cand in ("deepseek", "openai", "anthropic"):
            if _has_api_key(cand):
                save_settings({"provider": cand})
                break
    invalidate_llm_caches()
    return get_provider_status()


# 确保启动时加载磁盘配置
load_settings()
