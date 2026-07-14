"""模型供应商查询、切换与配置 API"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.models.provider import (
    get_provider_status,
    set_current_provider,
    update_llm_config,
)

models_router: APIRouter = APIRouter(prefix="/api", tags=["models"])


class ProviderSwitchRequest(BaseModel):
    provider: str = Field(..., description="deepseek / openai / anthropic")


class ProviderConfigBlock(BaseModel):
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None


class LLMConfigRequest(BaseModel):
    """保存模型配置（api_key 传掩码或空则保留原值）"""
    provider: str | None = None
    deepseek: ProviderConfigBlock | None = None
    openai: ProviderConfigBlock | None = None
    anthropic: ProviderConfigBlock | None = None


@models_router.get("/models")
async def get_models() -> dict[str, Any]:
    """当前模型 + 可选列表 + 掩码后的配置"""
    return get_provider_status()


@models_router.post("/models/provider")
async def switch_provider(body: ProviderSwitchRequest) -> dict[str, Any]:
    """切换当前供应商（须已配置 Key）"""
    try:
        return set_current_provider(body.provider)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@models_router.put("/models/config")
async def put_models_config(body: LLMConfigRequest) -> dict[str, Any]:
    """保存 API Key / 模型名 / Base URL，并可选切换默认供应商"""
    try:
        payload = body.model_dump(exclude_none=True)
        # 将嵌套 Pydantic 已 dump 的 dict 直接保存
        return update_llm_config(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
