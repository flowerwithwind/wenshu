"""知识库管理路由 — 按数据源隔离"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.datasources.sqlite_ds import BUILTIN_SQLITE_ID
from app.services.knowledge_manager import (
    add_domain_mapping,
    add_example,
    add_synonym,
    delete_domain_mapping,
    delete_example,
    delete_synonym,
    get_stats,
    load_knowledge,
    update_example,
)

knowledge_router: APIRouter = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


def _ds(datasource_id: str | None) -> str:
    return (datasource_id or BUILTIN_SQLITE_ID).strip() or BUILTIN_SQLITE_ID


class ExampleCreate(BaseModel):
    question: str
    sql: str
    tables: list[str] = []
    tags: list[str] = []
    datasource_id: str | None = None


class ExampleUpdate(BaseModel):
    question: str | None = None
    sql: str | None = None
    tables: list[str] | None = None
    tags: list[str] | None = None
    datasource_id: str | None = None


class SynonymCreate(BaseModel):
    synonyms: list[str]
    target_column: str
    table: str
    datasource_id: str | None = None


class DomainMappingCreate(BaseModel):
    term: str
    mapping: str
    table: str
    datasource_id: str | None = None


@knowledge_router.get("/")
async def get_knowledge(
    datasource_id: str | None = Query(default=None),
) -> dict[str, Any]:
    return load_knowledge(_ds(datasource_id))


@knowledge_router.get("/stats")
async def knowledge_stats(
    datasource_id: str | None = Query(default=None),
) -> dict[str, Any]:
    stats = get_stats(_ds(datasource_id))
    return stats


@knowledge_router.post("/examples")
async def create_example(body: ExampleCreate) -> dict[str, Any]:
    return add_example(
        body.question,
        body.sql,
        body.tables,
        body.tags,
        datasource_id=_ds(body.datasource_id),
    )


@knowledge_router.put("/examples/{index}")
async def update_example_route(index: int, body: ExampleUpdate) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        k: v
        for k, v in body.model_dump().items()
        if v is not None and k != "datasource_id"
    }
    try:
        return update_example(index, datasource_id=_ds(body.datasource_id), **kwargs)
    except IndexError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@knowledge_router.delete("/examples/{index}")
async def delete_example_route(
    index: int,
    datasource_id: str | None = Query(default=None),
) -> dict[str, str]:
    if delete_example(index, datasource_id=_ds(datasource_id)):
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="示例不存在")


@knowledge_router.post("/synonyms")
async def create_synonym(body: SynonymCreate) -> dict[str, Any]:
    return add_synonym(
        body.synonyms,
        body.target_column,
        body.table,
        datasource_id=_ds(body.datasource_id),
    )


@knowledge_router.delete("/synonyms/{index}")
async def delete_synonym_route(
    index: int,
    datasource_id: str | None = Query(default=None),
) -> dict[str, str]:
    if delete_synonym(index, datasource_id=_ds(datasource_id)):
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="同义词不存在")


@knowledge_router.post("/domain-mappings")
async def create_domain_mapping(body: DomainMappingCreate) -> dict[str, Any]:
    return add_domain_mapping(
        body.term,
        body.mapping,
        body.table,
        datasource_id=_ds(body.datasource_id),
    )


@knowledge_router.delete("/domain-mappings/{index}")
async def delete_domain_mapping_route(
    index: int,
    datasource_id: str | None = Query(default=None),
) -> dict[str, str]:
    if delete_domain_mapping(index, datasource_id=_ds(datasource_id)):
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="领域映射不存在")
