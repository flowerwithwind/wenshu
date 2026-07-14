"""
LLM 运行时配置 — 持久化到 data/llm_settings.json
用户可通过前端配置，无需手改 .env
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from app.config import (
    BACKEND_ROOT,
    LLM_PROVIDER,
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_MODEL,
    ANTHROPIC_API_KEY,
    ANTHROPIC_MODEL,
)
from app.logger import get_logger

logger = get_logger(__name__)

SETTINGS_PATH: Path = BACKEND_ROOT / "data" / "llm_settings.json"
_lock = threading.Lock()

# 内存中的完整配置（含明文 key，仅服务端使用）
_settings: dict[str, Any] = {}


def _default_settings() -> dict[str, Any]:
    return {
        "provider": (LLM_PROVIDER or "deepseek").lower(),
        "deepseek": {
            "api_key": DEEPSEEK_API_KEY or "",
            "base_url": DEEPSEEK_BASE_URL or "https://api.deepseek.com/v1",
            "model": DEEPSEEK_MODEL or "deepseek-chat",
        },
        "openai": {
            "api_key": OPENAI_API_KEY or "",
            "base_url": OPENAI_BASE_URL or "https://api.openai.com/v1",
            "model": OPENAI_MODEL or "gpt-4o",
        },
        "anthropic": {
            "api_key": ANTHROPIC_API_KEY or "",
            "base_url": "",
            "model": ANTHROPIC_MODEL or "claude-sonnet-4-20250514",
        },
    }


def _mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return key[:4] + "*" * min(12, len(key) - 8) + key[-4:]


def load_settings() -> dict[str, Any]:
    """加载配置：文件覆盖默认值（env 作为默认）"""
    global _settings
    with _lock:
        base = _default_settings()
        if SETTINGS_PATH.exists():
            try:
                raw = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    if raw.get("provider"):
                        base["provider"] = str(raw["provider"]).lower()
                    for name in ("deepseek", "openai", "anthropic"):
                        if isinstance(raw.get(name), dict):
                            for k, v in raw[name].items():
                                if v is not None and str(v).strip() != "":
                                    base[name][k] = str(v).strip()
            except Exception as e:
                logger.warning(f"读取 llm_settings.json 失败，使用默认: {e}")
        _settings = base
        return dict(_settings)


def get_settings() -> dict[str, Any]:
    if not _settings:
        return load_settings()
    with _lock:
        return dict(_settings)


def get_provider_config(provider: str) -> dict[str, str]:
    s = get_settings()
    return dict(s.get(provider.lower(), {}))


def get_active_provider() -> str:
    return get_settings().get("provider", "deepseek")


def save_settings(update: dict[str, Any]) -> dict[str, Any]:
    """
    保存/合并配置。
    update 可含:
      provider: str
      deepseek/openai/anthropic: {api_key?, base_url?, model?}
    api_key 若传空字符串或仅含 * 则保留原 key
    """
    global _settings
    with _lock:
        current = dict(_settings) if _settings else _default_settings()
        if not current:
            current = _default_settings()

        if update.get("provider"):
            current["provider"] = str(update["provider"]).lower().strip()

        for name in ("deepseek", "openai", "anthropic"):
            if not isinstance(update.get(name), dict):
                continue
            block = dict(current.get(name) or {})
            incoming = update[name]
            for field in ("api_key", "base_url", "model"):
                if field not in incoming:
                    continue
                val = incoming[field]
                if val is None:
                    continue
                val_s = str(val).strip()
                if field == "api_key":
                    # 空或带 * 的掩码 → 保留原 key
                    if not val_s or "*" in val_s:
                        continue
                    block["api_key"] = val_s
                else:
                    if val_s:
                        block[field] = val_s
            current[name] = block

        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_PATH.write_text(
            json.dumps(current, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        _settings = current
        logger.info(f"LLM 配置已保存 provider={current.get('provider')}")
        return dict(current)


def public_settings() -> dict[str, Any]:
    """给前端的配置（api_key 掩码）"""
    s = get_settings()
    out: dict[str, Any] = {"provider": s.get("provider", "deepseek")}
    for name in ("deepseek", "openai", "anthropic"):
        block = s.get(name) or {}
        key = block.get("api_key") or ""
        out[name] = {
            "api_key_masked": _mask_key(key),
            "has_key": bool(key),
            "base_url": block.get("base_url") or "",
            "model": block.get("model") or "",
        }
    return out


# 启动时加载一次
load_settings()
