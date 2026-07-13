"""
Agent 工具集 —— 供 ReAct Agent 调用的 LangChain Tool 定义
"""
from __future__ import annotations

from langchain_core.tools import tool
from app.nl2sql.database import (
    get_schema_info as db_get_schema_info,
    execute_sql as db_execute_sql,
    get_connection,
)
from app.config import DATASET_DIR
import json
import os


def _get_rag_retriever():
    """懒加载 RAG retriever，避免循环导入"""
    from app.rag.pipeline import get_pipeline
    pipeline = get_pipeline()
    return pipeline.retriever


@tool
def get_schema_info(table_name: str = "") -> str:
    """获取数据库表结构信息。传入空字符串获取全部表，或传入具体表名获取单表详情。
    返回：表名、列名、列类型、示例数据行、表关联关系。"""
    try:
        schema: str = db_get_schema_info()
        if table_name:
            # 只返回指定表的信息
            lines: list[str] = schema.split("\n")
            result_lines: list[str] = []
            in_target: bool = False
            for line in lines:
                if line.startswith("表 [") and table_name in line:
                    in_target = True
                elif line.startswith("表 ["):
                    in_target = False
                if in_target:
                    result_lines.append(line)
            if not result_lines:
                return f"未找到表 [{table_name}]。可用的表：customers, products, orders, monthly_targets, refunds"
            return "\n".join(result_lines)
        return schema
    except Exception as e:
        return f"获取 Schema 失败: {e}"


@tool
def get_table_sample(table_name: str, limit: int = 3) -> str:
    """获取指定表的前 N 行样本数据，用于快速了解数据分布和实际值。
    参数 table_name 为必填（如 'orders'），limit 默认为 3。"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM [{table_name}] LIMIT {min(limit, 10)}")
        columns: list[str] = [desc[0] for desc in cursor.description] if cursor.description else []
        rows: list[dict] = [dict(row) for row in cursor.fetchall()]
        conn.close()

        if not rows:
            return f"表 [{table_name}] 存在但无数据"

        result: str = f"表 [{table_name}] 样本数据（共取 {len(rows)} 行）：\n列: {', '.join(columns)}\n"
        for i, row in enumerate(rows, 1):
            # 只取前 5 列展示，避免过长
            preview: dict = {k: v for k, v in row.items()}
            result += f"  {i}. {preview}\n"
        return result
    except Exception as e:
        return f"获取样本失败: {e}"


@tool
def execute_sql(sql: str) -> str:
    """在 SQLite 数据库上执行只读 SELECT 查询。
    返回 JSON 格式的结果，包含 columns（列名列表）、row_count（行数）、rows（数据行，最多展示前 50 行）。
    如果 SQL 执行出错，返回错误信息。"""
    try:
        rows, columns = db_execute_sql(sql)
        if not rows:
            return json.dumps({
                "columns": columns,
                "row_count": 0,
                "rows": [],
                "message": "查询成功但无匹配数据，请检查查询条件"
            }, ensure_ascii=False)

        result: dict = {
            "columns": columns,
            "row_count": len(rows),
            "rows": rows[:50],
        }
        if len(rows) > 50:
            result["message"] = f"结果共 {len(rows)} 行，仅展示前 50 行"
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e), "sql": sql}, ensure_ascii=False)


@tool
def search_knowledge(query: str) -> str:
    """搜索领域知识库，获取与查询相关的 Few-shot 示例、同义词映射、领域术语解释。
    返回匹配度最高的知识片段。"""
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


# 工具列表，供 Agent 注册使用
AGENT_TOOLS = [
    get_schema_info,
    get_table_sample,
    execute_sql,
    search_knowledge,
]
