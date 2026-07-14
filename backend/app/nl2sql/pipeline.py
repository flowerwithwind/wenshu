"""
NL2SQL Pipeline - 以 NL2SQL 为主，RAG 为辅助的查询流程

流程:
1. 用户提问
2. RAG 检索相关 Schema 和上下文（辅助理解问题意图）
3. NL2SQL 翻译器生成 SQL
4. 执行 SQL 查询数据库
5. 基于查询结果生成自然语言回答 + 图表数据
"""
from __future__ import annotations

import time
import uuid
import json
import re
from typing import Any, Generator
from app.nl2sql.database import init_database, get_schema_info, execute_sql, is_database_ready
from app.nl2sql.translator import NL2SQLTranslator, AnswerGenerator
from app.nl2sql.corrector import SQLCorrector
from app.models.schemas import SourceDocument
from app.services.cache import get_cache, set_cache
from app.services.semantic_cache import get_semantic_cache
from app.nl2sql.intent import IntentClassifier, Intent
from app.nl2sql.multi_turn import get_multi_turn_manager, ConversationContext, MultiTurnManager
from app.agent.agent import get_agent
from app.logger import get_logger
from app.tracing import get_tracer
from app.datasources.registry import get_datasource, execute_with_audit
from app.datasources.context import set_current_datasource


logger = get_logger(__name__)


class NL2SQLPipeline:
    """NL2SQL 主流程编排器，RAG 作为辅助"""

    def __init__(self, rag_retriever=None) -> None:
        """
        Args:
            rag_retriever: RAG 检索器（可选），用于辅助理解问题意图
        """
        self.rag_retriever = rag_retriever
        self.translator: NL2SQLTranslator | None = None
        self.answer_generator: AnswerGenerator | None = None
        self._last_sql: str = ""
        self._last_sql_result: dict[str, Any] | None = None
        self._last_sources: list[SourceDocument] = []
        self._last_chart_data: dict[str, Any] | None = None
        self._last_has_numeric_data: bool = False
        self._last_response_time_ms: float = 0.0
        self._last_message_id: str = ""
        self._last_tool_calls: list[dict[str, Any]] = []
        self._init_components()

    def _init_components(self) -> None:
        """初始化组件"""
        try:
            self.translator = NL2SQLTranslator()
            self.answer_generator = AnswerGenerator()
            logger.info("NL2SQL 翻译器: 就绪")
        except ValueError as e:
            logger.warning(f"NL2SQL 警告: {e}")
            self.translator = None
            self.answer_generator = None

    def _get_rag_context(self, question: str) -> tuple[str, list]:
        """通过 RAG 检索辅助上下文"""
        if self.rag_retriever:
            with get_tracer().start_as_current_span("rag_retrieve") as span:
                span.set_attribute("question", question[:100])
                context, docs = self.rag_retriever.retrieve_with_context(question)
                span.set_attribute("docs_count", len(docs))
            return context, docs
        return "", []

    def query(
        self,
        question: str,
        conversation_id: str | None = None,
        datasource_id: str | None = None,
    ) -> dict[str, Any]:
        """执行 NL2SQL 查询"""
        tracer = get_tracer()
        start_time: float = time.time()
        conv_id: str = conversation_id or str(uuid.uuid4())
        ds = get_datasource(datasource_id)
        set_current_datasource(ds, datasource_id)

        if not self.translator:
            return {
                "id": str(uuid.uuid4()),
                "question": question,
                "answer": "NL2SQL 模型服务未配置，请设置 DEEPSEEK_API_KEY 环境变量。",
                "sources": [],
                "conversation_id": conv_id,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "response_time_ms": 0,
                "has_numeric_data": False,
                "chart_data": None,
                "sql": "",
                "sql_result": None,
            }

        # Step 0: 语义缓存检查（基于 embedding 相似度）
        semantic_cache = get_semantic_cache()
        cached = semantic_cache.get(question)
        if cached:
            logger.debug(f"语义缓存命中: {question[:50]}...")
            elapsed_ms = (time.time() - start_time) * 1000
            return {
                "id": str(uuid.uuid4()),
                "question": question,
                "answer": cached["answer"],
                "sources": cached.get("sources", []),
                "conversation_id": cached.get("conversation_id", conv_id),
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "response_time_ms": round(elapsed_ms, 2),
                "has_numeric_data": cached.get("has_numeric_data", False),
                "chart_data": cached.get("chart_data"),
                "sql": cached.get("sql", ""),
                "sql_result": cached.get("sql_result"),
            }

        # Step 0.5: 精确缓存检查
        cached = get_cache(question)
        if cached:
            logger.debug(f"Cache Hit: {question[:50]}...")
            # 同步到语义缓存，使相似问题也可命中
            semantic_cache.set(question, cached)
            elapsed_ms: float = (time.time() - start_time) * 1000
            return {
                "id": str(uuid.uuid4()),
                "question": question,
                "answer": cached["answer"],
                "sources": cached.get("sources", []),
                "conversation_id": cached.get("conversation_id", conv_id),
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "response_time_ms": round(elapsed_ms, 2),
                "has_numeric_data": cached.get("has_numeric_data", False),
                "chart_data": cached.get("chart_data"),
                "sql": cached.get("sql", ""),
                "sql_result": cached.get("sql_result"),
            }

        # Step 1: RAG 辅助检索（获取上下文，用于回退和来源展示）
        schema: str = ds.get_schema_info()
        rag_context, rag_docs = self._get_rag_context(question)

        intent: Intent = IntentClassifier.classify(question)

        if intent == Intent.CHITCHAT:
            return self._handle_chitchat(question, conv_id)
        elif intent == Intent.META:
            return self._handle_meta(question, conv_id, ds)
        elif intent == Intent.KNOWLEDGE_QA:
            return self._fallback_rag(question, conv_id, rag_context, rag_docs, start_time)

        # Step 1.5: 多轮对话上下文（支持从持久化恢复）
        mtm: MultiTurnManager = get_multi_turn_manager()
        conv_ctx: ConversationContext = mtm.get_context(conv_id, hydrate=True)
        history_prompt: str = conv_ctx.get_context_prompt() if conv_ctx.turns else ""

        # Step 2: NL2SQL 翻译（RAG 上下文作为 few-shot 示例辅助）
        with tracer.start_as_current_span("nl2sql_translate") as span:
            span.set_attribute("question", question[:200])
            sql: str = self.translator.translate(question, schema, rag_context, history_prompt)
            span.set_attribute("sql_length", len(sql))
            span.set_attribute("is_valid", str(self.translator._is_valid_sql(sql)))

        if not sql or not self.translator._is_valid_sql(sql):
            # 无法翻译为 SQL，回退到纯 RAG 模式
            logger.warning(f"NL2SQL 无法翻译，回退到 RAG 模式。SQL: {sql[:100] if sql else '空'}")
            return self._fallback_rag(question, conv_id, rag_context, rag_docs, start_time)

        # Step 3: 执行 SQL（带自动纠错循环）
        corrector: SQLCorrector = SQLCorrector(max_retries=3)
        correction_history: str = ""
        sql_succeeded: bool = False

        while not sql_succeeded:
            with tracer.start_as_current_span("sql_execute") as span:
                span.set_attribute("sql", sql[:200])
                span.set_attribute("correction_attempt", corrector.attempt_count)
                try:
                    rows, columns = execute_with_audit(ds, sql, source="pipeline")
                    span.set_attribute("row_count", len(rows))
                    span.set_attribute("success", True)
                    sql_succeeded = True
                except Exception as e:
                    error_str: str = str(e)
                    span.set_attribute("success", False)
                    span.set_attribute("error", error_str[:200])

                    if corrector.exhausted:
                        logger.warning(f"SQL 自纠错已耗尽({corrector.max_retries}次), 回退 RAG")
                        return self._fallback_rag(
                            question, conv_id, rag_context, rag_docs, start_time,
                            sql_error=error_str, sql=sql,
                        )

                    corrected: str = corrector.correct(
                        question, sql, error_str, schema, correction_history,
                    )
                    if not corrected or not corrected.strip().upper().startswith("SELECT"):
                        return self._fallback_rag(
                            question, conv_id, rag_context, rag_docs, start_time,
                            sql_error=error_str, sql=sql,
                        )

                    correction_history += f"尝试{corrector.attempt_count}: SQL={sql}\n  错误={error_str}\n"
                    sql = corrected
                    logger.info(f"SQL 自纠错 第{corrector.attempt_count}次 → 重试")

        # Step 4: 生成自然语言回答
        with tracer.start_as_current_span("answer_generate") as span:
            span.set_attribute("sql", sql[:200])
            span.set_attribute("row_count", len(rows))
            result: dict[str, Any] = self.answer_generator.generate(question, sql, columns, rows)
            span.set_attribute("answer_length", len(result.get("answer", "")))
            span.set_attribute("has_chart", str(result.get("chart_data") is not None))

        # Step 4.5: 记录多轮对话上下文
        conv_ctx.add_turn(question, sql, result["answer"])

        elapsed_ms: float = (time.time() - start_time) * 1000

        sources: list[SourceDocument] = [
            SourceDocument(
                content=doc.page_content[:200],
                source=doc.metadata.get("source", ""),
                score=doc.metadata.get("score"),
                metadata=doc.metadata,
            )
            for doc in rag_docs
        ]

        response: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "question": question,
            "answer": result["answer"],
            "sources": sources,
            "conversation_id": conv_id,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "response_time_ms": round(elapsed_ms, 2),
            "has_numeric_data": result.get("chart_data") is not None,
            "chart_data": result.get("chart_data"),
            "sql": sql,
            "sql_result": {"columns": columns, "rows": rows, "row_count": len(rows)},
        }

        # 缓存结果（精确 + 语义）
        set_cache(question, response)
        semantic_cache.set(question, response)

        return response


    def _reset_stream_state(self, message_id: str | None = None) -> None:
        """重置流式查询的副作用字段"""
        self._last_message_id = message_id or str(uuid.uuid4())
        self._last_sql = ""
        self._last_sql_result = None
        self._last_sources = []
        self._last_chart_data = None
        self._last_has_numeric_data = False
        self._last_response_time_ms = 0.0
        self._last_tool_calls = []

    def _apply_cached_to_stream_state(
        self,
        cached: dict[str, Any],
        start_time: float,
        conv_id: str,
    ) -> str:
        """将缓存结果写入流式副作用字段，返回回答文本"""
        self._last_sql = cached.get("sql", "") or ""
        self._last_sql_result = cached.get("sql_result")
        sources = cached.get("sources") or []
        self._last_sources = [
            s if isinstance(s, SourceDocument) else SourceDocument(
                content=s.get("content", "") if isinstance(s, dict) else str(s),
                source=s.get("source", "") if isinstance(s, dict) else "",
                score=s.get("score") if isinstance(s, dict) else None,
                metadata=s.get("metadata", {}) if isinstance(s, dict) else {},
            )
            for s in sources
        ]
        self._last_chart_data = cached.get("chart_data")
        self._last_has_numeric_data = cached.get(
            "has_numeric_data",
            cached.get("chart_data") is not None,
        )
        self._last_response_time_ms = round((time.time() - start_time) * 1000, 2)
        return cached.get("answer", "") or ""

    def query_stream(
        self,
        question: str,
        conversation_id: str | None = None,
        datasource_id: str | None = None,
    ) -> Generator[str, None, None]:
        """流式 NL2SQL 查询 — 与 query() 对齐：缓存 / 意图 / 多轮 / 纠错 / RAG 回退"""
        start_time: float = time.time()
        conv_id: str = conversation_id or str(uuid.uuid4())
        self._reset_stream_state()
        ds = get_datasource(datasource_id)
        set_current_datasource(ds, datasource_id)

        if not self.translator or not self.answer_generator:
            yield "NL2SQL 模型服务未配置，请设置 DEEPSEEK_API_KEY 环境变量。"
            self._last_response_time_ms = round((time.time() - start_time) * 1000, 2)
            return

        # Step 0: 语义缓存
        semantic_cache = get_semantic_cache()
        cached = semantic_cache.get(question)
        if cached:
            logger.debug(f"流式语义缓存命中: {question[:50]}...")
            answer = self._apply_cached_to_stream_state(cached, start_time, conv_id)
            if answer:
                yield answer
            return

        # Step 0.5: 精确缓存
        cached = get_cache(question)
        if cached:
            logger.debug(f"流式精确缓存命中: {question[:50]}...")
            semantic_cache.set(question, cached)
            answer = self._apply_cached_to_stream_state(cached, start_time, conv_id)
            if answer:
                yield answer
            return

        # Step 1: RAG + 意图
        schema: str = ds.get_schema_info()
        rag_context, rag_docs = self._get_rag_context(question)
        intent: Intent = IntentClassifier.classify(question)

        if intent == Intent.CHITCHAT:
            result = self._handle_chitchat(question, conv_id)
            self._last_response_time_ms = round((time.time() - start_time) * 1000, 2)
            yield result["answer"]
            return

        if intent == Intent.META:
            result = self._handle_meta(question, conv_id, ds)
            self._last_response_time_ms = round((time.time() - start_time) * 1000, 2)
            yield result["answer"]
            return

        if intent == Intent.KNOWLEDGE_QA:
            result = self._fallback_rag(question, conv_id, rag_context, rag_docs, start_time)
            self._last_sources = result.get("sources") or []
            self._last_response_time_ms = result.get("response_time_ms", 0)
            yield result["answer"]
            return

        # Step 1.5: 多轮（支持从持久化恢复）
        mtm: MultiTurnManager = get_multi_turn_manager()
        conv_ctx: ConversationContext = mtm.get_context(conv_id, hydrate=True)
        history_prompt: str = conv_ctx.get_context_prompt() if conv_ctx.turns else ""

        # Step 2: NL2SQL 翻译
        with get_tracer().start_as_current_span("nl2sql_translate") as span:
            span.set_attribute("question", question[:200])
            sql: str = self.translator.translate(question, schema, rag_context, history_prompt)
            span.set_attribute("sql_length", len(sql))
            span.set_attribute("is_valid", str(self.translator._is_valid_sql(sql)))

        if not sql or not self.translator._is_valid_sql(sql):
            logger.warning(f"流式 NL2SQL 无法翻译，回退 RAG。SQL: {sql[:100] if sql else '空'}")
            result = self._fallback_rag(question, conv_id, rag_context, rag_docs, start_time, sql=sql or "")
            self._last_sql = result.get("sql", "") or ""
            self._last_sources = result.get("sources") or []
            self._last_response_time_ms = result.get("response_time_ms", 0)
            yield result["answer"]
            return

        # Step 3: 执行 SQL（带自动纠错）
        corrector: SQLCorrector = SQLCorrector(max_retries=3)
        correction_history: str = ""
        sql_succeeded: bool = False
        rows: list[dict[str, Any]] = []
        columns: list[str] = []

        while not sql_succeeded:
            with get_tracer().start_as_current_span("sql_execute") as span:
                span.set_attribute("sql", sql[:200])
                span.set_attribute("correction_attempt", corrector.attempt_count)
                try:
                    rows, columns = execute_with_audit(ds, sql, source="pipeline_stream")
                    span.set_attribute("row_count", len(rows))
                    sql_succeeded = True
                except Exception as e:
                    error_str: str = str(e)
                    span.set_attribute("error", error_str[:200])

                    if corrector.exhausted:
                        logger.warning("流式 SQL 自纠错已耗尽，回退 RAG")
                        result = self._fallback_rag(
                            question, conv_id, rag_context, rag_docs, start_time,
                            sql_error=error_str, sql=sql,
                        )
                        self._last_sql = sql
                        self._last_sources = result.get("sources") or []
                        self._last_response_time_ms = result.get("response_time_ms", 0)
                        yield result["answer"]
                        return

                    yield f"⚠️ SQL 执行出错，正在自动修正（第{corrector.attempt_count + 1}次）...\n\n"

                    corrected: str = corrector.correct(
                        question, sql, error_str, schema, correction_history,
                    )
                    if not corrected or not corrected.strip().upper().startswith("SELECT"):
                        result = self._fallback_rag(
                            question, conv_id, rag_context, rag_docs, start_time,
                            sql_error=error_str, sql=sql,
                        )
                        self._last_sql = sql
                        self._last_sources = result.get("sources") or []
                        self._last_response_time_ms = result.get("response_time_ms", 0)
                        yield result["answer"]
                        return

                    correction_history += f"尝试{corrector.attempt_count}: SQL={sql}\n  错误={error_str}\n"
                    sql = corrected
                    logger.info(f"流式 SQL 自纠错 第{corrector.attempt_count}次 → 重试")

        self._last_sql = sql
        self._last_sql_result = {"columns": columns, "rows": rows, "row_count": len(rows)}

        # Step 4: 流式生成回答
        full_answer: str = ""
        with get_tracer().start_as_current_span("answer_stream") as span:
            span.set_attribute("sql", sql[:200])
            span.set_attribute("row_count", len(rows))
            for chunk in self.answer_generator.generate_stream(question, sql, columns, rows):
                full_answer += chunk
                yield chunk
            span.set_attribute("answer_length", len(full_answer))

        conv_ctx.add_turn(question, sql, full_answer)

        self._last_sources = [
            SourceDocument(
                content=doc.page_content[:200],
                source=doc.metadata.get("source", ""),
                score=doc.metadata.get("score"),
                metadata=doc.metadata,
            )
            for doc in rag_docs
        ]
        self._last_response_time_ms = round((time.time() - start_time) * 1000, 2)
        self._last_chart_data = self._extract_chart_data(full_answer)
        self._last_has_numeric_data = self._last_chart_data is not None

        cache_payload: dict[str, Any] = {
            "id": self._last_message_id,
            "question": question,
            "answer": full_answer,
            "sources": self._last_sources,
            "conversation_id": conv_id,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "response_time_ms": self._last_response_time_ms,
            "has_numeric_data": self._last_has_numeric_data,
            "chart_data": self._last_chart_data,
            "sql": sql,
            "sql_result": self._last_sql_result,
        }
        set_cache(question, cache_payload)
        semantic_cache.set(question, cache_payload)

    def _handle_chitchat(self, question: str, conv_id: str) -> dict[str, Any]:
        """处理闲聊"""
        greetings: dict[str, str] = {
            "你好": "你好！我是智能问数助手，可以帮你查询和分析电商数据。试试问我'销售额最高的品类是什么？'",
            "谢谢": "不客气！随时可以继续提问。",
            "再见": "再见！期待下次为你服务。",
            "你是谁": "我是智能问数助手，基于 NL2SQL + RAG 架构，可以帮你查询和分析电商数据库中的订单、客户、商品、退款等数据。",
            "你能做什么": "我可以帮你：\n1. 查询销售额、订单数、客户数等数据\n2. 分析各品类、省份、会员等级的销售表现\n3. 计算退款率、折扣率、达成率等指标\n4. 生成趋势图、排名图、饼图等可视化\n\n试试问我'2024年各月销售额趋势'吧！",
            "介绍一下": "这是智能问数系统，一个基于自然语言的数据查询工具。你只需用中文提问，系统会自动翻译为 SQL 查询数据库，并返回清晰的分析结果和图表。",
            "hello": "Hello! I'm a Smart QA assistant for e-commerce data. How can I help you with your data analysis?",
            "hi": "Hi there! I can help you explore sales, customer, and product data. What would you like to know?",
        }

        q_lower: str = question.lower().strip()
        answer: str | None = None
        for key, response in greetings.items():
            if key in q_lower:
                answer = response
                break

        if not answer:
            answer = "你好！有什么数据相关的问题我可以帮你解答吗？"

        return {
            "id": str(uuid.uuid4()),
            "question": question,
            "answer": answer,
            "sources": [],
            "conversation_id": conv_id,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "response_time_ms": 0,
            "has_numeric_data": False,
            "chart_data": None,
            "sql": "",
            "sql_result": None,
        }

    def _handle_meta(self, question: str, conv_id: str, ds=None) -> dict[str, Any]:
        """处理系统元问题"""
        if ds is None:
            ds = get_datasource(None)
        schema: str = ds.get_schema_info()
        answer: str = (
            f"当前数据源：**{ds.meta.name}**（{ds.meta.type}）\n\n"
            f"包含以下表：\n\n{schema}\n\n"
            f"你可以直接问我数据分析相关的问题。"
        )

        return {
            "id": str(uuid.uuid4()),
            "question": question,
            "answer": answer,
            "sources": [],
            "conversation_id": conv_id,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "response_time_ms": 0,
            "has_numeric_data": False,
            "chart_data": None,
            "sql": "",
            "sql_result": None,
        }

    def _extract_chart_data(self, text: str) -> dict[str, Any] | None:
        """从回答文本中提取 chart_data JSON 块"""
        match = re.search(r'```chart_data\s*\n(.*?)\n```', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        return None

    def _fallback_rag(
        self,
        question: str,
        conv_id: str,
        rag_context: str,
        rag_docs: list,
        start_time: float,
        sql_error: str = "",
        sql: str = "",
    ) -> dict[str, Any]:
        """当 NL2SQL 无法处理时，回退到 RAG 模式"""
        from app.rag.generator import RAGGenerator

        elapsed_ms: float = (time.time() - start_time) * 1000

        sources: list[SourceDocument] = [
            SourceDocument(
                content=doc.page_content[:200],
                source=doc.metadata.get("source", ""),
                score=doc.metadata.get("score"),
                metadata=doc.metadata,
            )
            for doc in rag_docs
        ]

        error_hint: str = ""
        if sql_error:
            error_hint = f"\n\n> 尝试了 SQL 查询但未成功: {sql_error}"

        try:
            generator: RAGGenerator = RAGGenerator()
            answer: str = generator.generate(
                question,
                rag_context,
                rag_docs,
            )["answer"]
            answer += error_hint
        except Exception:
            answer = f"根据现有数据，我无法直接回答该问题。{error_hint}"

        return {
            "id": str(uuid.uuid4()),
            "question": question,
            "answer": answer,
            "sources": sources,
            "conversation_id": conv_id,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "response_time_ms": round(elapsed_ms, 2),
            "has_numeric_data": False,
            "chart_data": None,
            "sql": sql,
            "sql_result": None,
        }

    def get_stats(self) -> dict[str, Any]:
        """获取系统状态（rag_ready 需向量库真正可用，不能仅看 retriever 对象）"""
        rag_ready: bool = False
        if self.rag_retriever is not None:
            vsm = getattr(self.rag_retriever, "vsm", None)
            if vsm is not None and getattr(vsm, "is_ready", lambda: False)():
                rag_ready = True
        return {
            "nl2sql_ready": self.translator is not None,
            "database_ready": is_database_ready(),
            "rag_ready": rag_ready,
        }

    def query_agent(
        self,
        question: str,
        conversation_id: str | None = None,
        datasource_id: str | None = None,
    ) -> dict[str, Any]:
        start_time: float = time.time()
        conv_id: str = conversation_id or str(uuid.uuid4())
        ds = get_datasource(datasource_id)
        set_current_datasource(ds, datasource_id)
        cached = get_semantic_cache().get(question)
        if cached:
            elapsed_ms: float = (time.time() - start_time) * 1000
            cached["response_time_ms"] = round(elapsed_ms, 2)
            cached["conversation_id"] = conv_id
            return cached
        cached = get_cache(question)
        if cached:
            elapsed_ms: float = (time.time() - start_time) * 1000
            cached["response_time_ms"] = round(elapsed_ms, 2)
            cached["conversation_id"] = conv_id
            get_semantic_cache().set(question, cached)
            return cached
        intent: Intent = IntentClassifier.classify(question)
        if intent == Intent.CHITCHAT:
            return self._handle_chitchat(question, conv_id)
        if intent == Intent.META:
            return self._handle_meta(question, conv_id, ds)
        try:
            agent = get_agent()
            result: dict[str, Any] = agent.query(question, conv_id)
            result["conversation_id"] = result.get("conversation_id", conv_id)
            get_semantic_cache().set(question, result)
            return result
        except ValueError as e:
            logger.warning(f"Agent 不可用 ({e})，回退到 Pipeline 模式")
            return self.query(question, conversation_id, datasource_id)


    def query_agent_stream(
        self,
        question: str,
        conversation_id: str | None = None,
        datasource_id: str | None = None,
    ) -> Generator[str, None, None]:
        """Agent 流式；失败时回退 Pipeline，并统一为 Agent 事件协议"""
        ds = get_datasource(datasource_id)
        set_current_datasource(ds, datasource_id)
        try:
            agent = get_agent()
            yield from agent.query_stream(question, conversation_id)
            return
        except ValueError as e:
            logger.warning(f"Agent 不可用 ({e})，回退到 Pipeline 模式")

        conv_id: str = conversation_id or str(uuid.uuid4())
        full_answer: str = ""
        for chunk in self.query_stream(question, conv_id, datasource_id):
            full_answer += chunk
            yield json.dumps({"type": "chunk", "chunk": chunk}, ensure_ascii=False)

        yield json.dumps({
            "type": "done",
            "answer": full_answer,
            "chart_data": self._last_chart_data,
            "sql": self._last_sql,
            "sql_result": self._last_sql_result,
            "conversation_id": conv_id,
            "response_time_ms": self._last_response_time_ms,
            "iterations": 0,
            "tool_calls": [],
            "mode": "pipeline_fallback",
        }, ensure_ascii=False)


# 全局单例
_pipeline: NL2SQLPipeline | None = None


def get_nl2sql_pipeline(rag_retriever=None) -> NL2SQLPipeline:
    """获取 NL2SQL Pipeline 单例"""
    global _pipeline
    if _pipeline is None:
        _pipeline = NL2SQLPipeline(rag_retriever=rag_retriever)
    elif rag_retriever and _pipeline.rag_retriever is None:
        _pipeline.rag_retriever = rag_retriever
    return _pipeline
