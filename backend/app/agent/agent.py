"""
ReAct Agent —— 基于 LangChain bind_tools 实现的 SQL 数据分析 Agent

核心流程：
1. 用户提问 → LLM 决定调用哪些工具
2. 执行工具 → 结果返回 LLM
3. LLM 分析结果 → 可能调用更多工具（自纠错、深入查询）
4. 最终 LLM 生成完整回答（含图表数据）
"""
from __future__ import annotations

import time
import uuid
import json
import re
from typing import Any, Generator

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage

from app.models.provider import get_chat_model
from app.agent.prompts import AGENT_SYSTEM_PROMPT, AGENT_USER_TEMPLATE
from app.agent.tools import AGENT_TOOLS
from app.tracing import get_tracer

MAX_ITERATIONS: int = 10       # 最大 ReAct 迭代次数
MAX_SQL_RETRIES: int = 3       # SQL 执行失败最大重试次数


class SQAAgent:
    """ReAct 模式的 SQL 数据分析 Agent"""

    def __init__(self) -> None:
        self.llm: BaseChatModel = get_chat_model(temperature=0.1, max_tokens=4096)
        # 将工具绑定到 LLM，使其原生支持 function calling
        self.llm_with_tools = self.llm.bind_tools(AGENT_TOOLS)
        self._tool_map = {t.name: t for t in AGENT_TOOLS}

    def query(
        self,
        question: str,
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        """执行一次 Agent 查询（非流式），返回完整结果"""
        start_time: float = time.time()
        conv_id: str = conversation_id or str(uuid.uuid4())

        messages: list = self._build_initial_messages(question)

        sql_executed: str = ""
        sql_result: dict | None = None
        all_tool_calls: list[dict[str, Any]] = []
        sql_retry_count: int = 0
        last_sql_error: str = ""

        tracer = get_tracer()
        tracer.add_event("agent_query_start", {"question": question[:200]})
        for iteration in range(MAX_ITERATIONS):
            with tracer.start_as_current_span("agent_iteration") as span:
                span.set_attribute("iteration", iteration)
                response = self.llm_with_tools.invoke(messages)
                messages.append(response)

                tool_calls = getattr(response, "tool_calls", None)
                if not tool_calls:
                    # Agent 认为任务完成，生成最终回答
                    answer: str = response.content or ""
                    chart_data, answer = self._extract_chart_data(answer)

                    elapsed_ms: float = round((time.time() - start_time) * 1000, 2)
                    span.set_attribute("completed", True)
                    span.set_attribute("iterations_used", iteration + 1)
                    return self._build_response(
                        question=question,
                        answer=answer.strip(),
                        chart_data=chart_data,
                        sql=sql_executed,
                        sql_result=sql_result,
                        conv_id=conv_id,
                        elapsed_ms=elapsed_ms,
                        iterations=iteration + 1,
                        tool_calls=all_tool_calls,
                    )

                # 执行所有工具调用
                for tc in tool_calls:
                    tool_name: str = tc["name"]
                    tool_args: dict = tc.get("args", {})
                    tool_call_id: str = tc.get("id", str(uuid.uuid4()))

                    # 跟踪 SQL 重试
                    if tool_name == "execute_sql":
                        sql_retry_count += 1

                    with tracer.start_as_current_span(f"tool_{tool_name}") as tspan:
                        tspan.set_attribute("tool", tool_name)
                        result_str: str = self._execute_tool(tool_name, tool_args)
                        tspan.set_attribute("result_length", len(result_str))

                    # 记录 SQL 执行
                    if tool_name == "execute_sql":
                        try:
                            parsed: dict = json.loads(result_str)
                            if "error" in parsed:
                                last_sql_error = parsed["error"]
                                if sql_retry_count >= MAX_SQL_RETRIES:
                                    result_str = json.dumps({
                                        "error": parsed["error"],
                                        "retries_exhausted": True,
                                        "message": f"SQL 执行已失败 {sql_retry_count} 次，请直接告知用户当前无法查询该数据，并建议更具体的提问方式。"
                                    }, ensure_ascii=False)
                            else:
                                sql_executed = tool_args.get("sql", "")
                                sql_result = {
                                    "columns": parsed.get("columns", []),
                                    "rows": parsed.get("rows", []),
                                    "row_count": parsed.get("row_count", 0),
                                }
                                last_sql_error = ""
                                sql_retry_count = 0
                        except json.JSONDecodeError:
                            pass

                    all_tool_calls.append({
                        "tool": tool_name,
                        "args": tool_args,
                        "result_preview": result_str[:300],
                    })

                    messages.append(
                        ToolMessage(content=result_str, tool_call_id=tool_call_id)
                    )

        # 达到最大迭代次数，强制让 LLM 总结
        messages.append(HumanMessage(
            content="已达到最大推理步数，请基于已有的工具调用结果生成最终回答。"
        ))
        final_response = self.llm.invoke(messages)
        answer = final_response.content or ""
        chart_data, answer = self._extract_chart_data(answer)

        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        return self._build_response(
            question=question,
            answer=answer.strip(),
            chart_data=chart_data,
            sql=sql_executed,
            sql_result=sql_result,
            conv_id=conv_id,
            elapsed_ms=elapsed_ms,
            iterations=MAX_ITERATIONS,
            tool_calls=all_tool_calls,
        )

    def query_stream(
        self,
        question: str,
        conversation_id: str | None = None,
    ) -> Generator[str, None, None]:
        """执行 Agent 查询（流式），yield SSE 事件 JSON 字符串"""
        start_time: float = time.time()
        conv_id: str = conversation_id or str(uuid.uuid4())

        messages: list = self._build_initial_messages(question)

        sql_executed: str = ""
        sql_result: dict | None = None
        all_tool_calls: list[dict[str, Any]] = []
        sql_retry_count: int = 0

        for iteration in range(MAX_ITERATIONS):
            response = self.llm_with_tools.invoke(messages)
            messages.append(response)

            tool_calls = getattr(response, "tool_calls", None)
            if not tool_calls:
                answer = response.content or ""
                chart_data, answer = self._extract_chart_data(answer)

                elapsed_ms = round((time.time() - start_time) * 1000, 2)
                yield json.dumps({
                    "type": "done",
                    "answer": answer.strip(),
                    "chart_data": chart_data,
                    "sql": sql_executed,
                    "sql_result": sql_result,
                    "conversation_id": conv_id,
                    "response_time_ms": elapsed_ms,
                    "iterations": iteration + 1,
                    "tool_calls": all_tool_calls,
                }, ensure_ascii=False)
                return

            # 通知前端工具调用
            for tc in tool_calls:
                tool_name: str = tc["name"]
                tool_args: dict = tc.get("args", {})
                tool_call_id: str = tc.get("id", str(uuid.uuid4()))

                # 通知前端工具调用开始
                yield json.dumps({
                    "type": "tool_start",
                    "tool": tool_name,
                    "args": tool_args,
                }, ensure_ascii=False) + "\n"

                result_str: str = self._execute_tool(tool_name, tool_args)

                # 通知前端工具调用结果
                yield json.dumps({
                    "type": "tool_result",
                    "tool": tool_name,
                    "result_preview": result_str[:500],
                }, ensure_ascii=False) + "\n"

                if tool_name == "execute_sql":
                    sql_retry_count += 1
                    try:
                        parsed: dict = json.loads(result_str)
                        if "error" not in parsed:
                            sql_executed = tool_args.get("sql", "")
                            sql_result = {
                                "columns": parsed.get("columns", []),
                                "rows": parsed.get("rows", []),
                                "row_count": parsed.get("row_count", 0),
                            }
                    except json.JSONDecodeError:
                        pass

                all_tool_calls.append({
                    "tool": tool_name,
                    "args": tool_args,
                    "result_preview": result_str[:300],
                })

                messages.append(
                    ToolMessage(content=result_str, tool_call_id=tool_call_id)
                )

        # 达到最大迭代次数
        messages.append(HumanMessage(
            content="已达到最大推理步数，请基于已有的工具调用结果生成最终回答。"
        ))
        final_response = self.llm.invoke(messages)
        answer = final_response.content or ""
        chart_data, answer = self._extract_chart_data(answer)

        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        yield json.dumps({
            "type": "done",
            "answer": answer.strip(),
            "chart_data": chart_data,
            "sql": sql_executed,
            "sql_result": sql_result,
            "conversation_id": conv_id,
            "response_time_ms": elapsed_ms,
            "iterations": MAX_ITERATIONS,
            "tool_calls": all_tool_calls,
        }, ensure_ascii=False)

    def _build_initial_messages(self, question: str) -> list:
        """构建初始消息列表"""
        return [
            SystemMessage(content=AGENT_SYSTEM_PROMPT),
            HumanMessage(content=AGENT_USER_TEMPLATE.format(question=question)),
        ]

    def _execute_tool(self, tool_name: str, args: dict[str, Any]) -> str:
        """执行单个工具调用"""
        tool = self._tool_map.get(tool_name)
        if not tool:
            return json.dumps({"error": f"未知工具: {tool_name}"})
        try:
            result = tool.invoke(args)
            # 处理工具返回的非字符串结果
            if isinstance(result, dict):
                return json.dumps(result, ensure_ascii=False)
            return str(result)
        except Exception as e:
            return json.dumps({"error": str(e), "tool": tool_name})

    def _extract_chart_data(self, text: str) -> tuple[dict | None, str]:
        """从回答中提取 chart_data 并清理"""
        match = re.search(r'```chart_data\s*\n(.*?)\n```', text, re.DOTALL)
        chart_data: dict | None = None
        if match:
            try:
                chart_data = json.loads(match.group(1))
                text = re.sub(r'```chart_data\s*\n.*?\n```', '', text, flags=re.DOTALL).strip()
            except json.JSONDecodeError:
                pass
        return chart_data, text

    def _build_response(
        self,
        question: str,
        answer: str,
        chart_data: dict | None,
        sql: str,
        sql_result: dict | None,
        conv_id: str,
        elapsed_ms: float,
        iterations: int,
        tool_calls: list[dict],
    ) -> dict[str, Any]:
        """构建标准的查询响应"""
        return {
            "id": str(uuid.uuid4()),
            "question": question,
            "answer": answer,
            "sources": [],
            "conversation_id": conv_id,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "response_time_ms": elapsed_ms,
            "has_numeric_data": chart_data is not None,
            "chart_data": chart_data,
            "sql": sql,
            "sql_result": sql_result,
            # Agent 特有字段
            "mode": "agent",
            "iterations": iterations,
            "tool_calls": tool_calls,
        }


# 全局单例
_agent: SQAAgent | None = None


def get_agent() -> SQAAgent:
    """获取 Agent 单例"""
    global _agent
    if _agent is None:
        _agent = SQAAgent()
    return _agent
