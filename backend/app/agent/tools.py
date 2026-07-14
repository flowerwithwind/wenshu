"""
Agent 工具集 —— 基于当前请求数据源上下文执行
"""
from __future__ import annotations

import json

from langchain_core.tools import tool

from app.datasources.context import get_current_datasource
from app.datasources.registry import execute_with_audit


def _get_rag_retriever():
    from app.rag.pipeline import get_pipeline
    return get_pipeline().retriever


@tool
def get_schema_info(table_name: str = "") -> str:
    """获取数据库表结构信息。传入空字符串获取全部表，或传入具体表名获取单表详情。"""
    try:
        ds = get_current_datasource()
        schema: str = ds.get_schema_info()
        if table_name:
            lines: list[str] = schema.split("\n")
            result_lines: list[str] = []
            in_target: bool = False
            for line in lines:
                if line.startswith("表") and table_name in line:
                    in_target = True
                elif line.startswith("表") and in_target:
                    in_target = False
                if in_target:
                    result_lines.append(line)
            if not result_lines:
                return f"未找到表 {table_name}。完整 Schema:\n{schema[:1500]}"
            return "\n".join(result_lines)
        return schema
    except Exception as e:
        return f"获取 Schema 失败: {e}"


@tool
def get_table_sample(table_name: str, limit: int = 3) -> str:
    """获取指定表的前 N 行样本数据。"""
    try:
        ds = get_current_datasource()
        return ds.get_table_sample(table_name, limit=limit)
    except Exception as e:
        return f"获取样本失败: {e}"


@tool
def execute_sql(sql: str) -> str:
    """在当前数据源上执行只读 SELECT 查询。返回 JSON：columns/row_count/rows。"""
    try:
        ds = get_current_datasource()
        rows, columns = execute_with_audit(ds, sql, source="agent")
        if not rows:
            return json.dumps({
                "columns": columns,
                "row_count": 0,
                "rows": [],
                "message": "查询成功但无匹配数据，请检查查询条件",
                "datasource": ds.meta.name,
            }, ensure_ascii=False)

        result: dict = {
            "columns": columns,
            "row_count": len(rows),
            "rows": rows[:50],
            "datasource": ds.meta.name,
        }
        if len(rows) > 50:
            result["message"] = f"结果共 {len(rows)} 行，仅展示前 50 行"
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e), "sql": sql}, ensure_ascii=False)


@tool
def search_knowledge(query: str) -> str:
    """搜索领域知识库，获取 Few-shot 示例、同义词映射、领域术语解释。"""
    try:
        retriever = _get_rag_retriever()
        if not retriever:
            return "RAG 知识库未初始化，请先构建向量索引"

        context, docs = retriever.retrieve_with_context(query)
        if not docs:
            return f"未找到与 '{query}' 相关的知识片段"

        result: str = f"知识库检索结果（查询: {query}）:\n\n"
        for i, doc in enumerate(docs[:5], 1):
            score = doc.metadata.get("score", "N/A")
            source_type = doc.metadata.get("type", "未知")
            result += f"### 片段 {i} (类型: {source_type}, 相关度: {score})\n"
            result += f"{doc.page_content[:500]}\n\n"
        return result
    except Exception as e:
        return f"知识库检索失败: {e}"


AGENT_TOOLS = [
    get_schema_info,
    get_table_sample,
    execute_sql,
    search_knowledge,
]
