"""知识库管理路由"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.knowledge_manager import (
    load_knowledge, add_example, delete_example, update_example,
    add_synonym, delete_synonym, add_domain_mapping, delete_domain_mapping,
    get_stats
)

knowledge_router: APIRouter = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


class ExampleCreate(BaseModel):
    question: str
    sql: str
    tables: list[str] = []
    tags: list[str] = []


class ExampleUpdate(BaseModel):
    question: str | None = None
    sql: str | None = None
    tables: list[str] | None = None
    tags: list[str] | None = None


class SynonymCreate(BaseModel):
    synonyms: list[str]
    target_column: str
    table: str


class DomainMappingCreate(BaseModel):
    term: str
    mapping: str
    table: str


@knowledge_router.get("/")
async def get_knowledge() -> dict:
    """获取完整知识库"""
    return load_knowledge()


@knowledge_router.get("/stats")
async def knowledge_stats() -> dict:
    """获取知识库统计"""
    return get_stats()


@knowledge_router.post("/examples")
async def create_example(body: ExampleCreate) -> dict:
    """新增示例"""
    result: dict = add_example(body.question, body.sql, body.tables, body.tags)
    return result


@knowledge_router.put("/examples/{index}")
async def update_example_route(index: int, body: ExampleUpdate) -> dict:
    """更新示例"""
    kwargs: dict = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        result: dict = update_example(index, **kwargs)
        return result
    except IndexError as e:
        raise HTTPException(status_code=404, detail=str(e))


@knowledge_router.delete("/examples/{index}")
async def delete_example_route(index: int) -> dict:
    """删除示例"""
    if delete_example(index):
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="示例不存在")


@knowledge_router.post("/synonyms")
async def create_synonym(body: SynonymCreate) -> dict:
    """新增同义词"""
    result: dict = add_synonym(body.synonyms, body.target_column, body.table)
    return result


@knowledge_router.delete("/synonyms/{index}")
async def delete_synonym_route(index: int) -> dict:
    """删除同义词"""
    if delete_synonym(index):
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="同义词不存在")


@knowledge_router.post("/domain-mappings")
async def create_domain_mapping(body: DomainMappingCreate) -> dict:
    """新增领域映射"""
    result: dict = add_domain_mapping(body.term, body.mapping, body.table)
    return result


@knowledge_router.delete("/domain-mappings/{index}")
async def delete_domain_mapping_route(index: int) -> dict:
    """删除领域映射"""
    if delete_domain_mapping(index):
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="领域映射不存在")
