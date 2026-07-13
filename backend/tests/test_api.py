"""
API 测试 — 覆盖所有路由端点
使用 httpx AsyncClient 发送请求，mock LLM 和数据库层
"""
import pytest
import json
import os
import tempfile
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport
from app.main import app


# ===== 共享 Fixtures =====

@pytest.fixture
def client():
    """提供 FastAPI 测试客户端"""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture(autouse=True)
def mock_db():
    """Mock 数据库层，避免依赖真实 SQLite 文件"""
    with patch("app.nl2sql.database.is_database_ready", return_value=True):
        with patch("app.nl2sql.database.get_schema_info", return_value="表 [orders]: 订单ID, 金额\n表 [customers]: 客户ID, 姓名"):
            with patch("app.nl2sql.database.execute_sql", return_value=(
                [{"订单ID": 1, "金额": 100}], ["订单ID", "金额"]
            )):
                with patch("app.nl2sql.database.init_database"):
                    yield


@pytest.fixture
def mock_translator():
    """Mock NL2SQL 翻译器"""
    with patch("app.nl2sql.translator.NL2SQLTranslator") as mock:
        instance = mock.return_value
        instance.translate.return_value = "SELECT * FROM [orders] LIMIT 5"
        instance._is_valid_sql.return_value = True
        yield instance


@pytest.fixture
def mock_answer_generator():
    """Mock 回答生成器"""
    with patch("app.nl2sql.translator.AnswerGenerator") as mock:
        instance = mock.return_value
        instance.generate.return_value = {
            "answer": "查询结果显示订单ID为1，金额为100元。",
            "chart_data": None,
        }
        instance.generate_stream.return_value = iter(["这是", "流式", "回答"])
        yield instance


@pytest.fixture
def mock_rag_pipeline():
    """Mock RAG Pipeline"""
    with patch("app.rag.pipeline.RAGPipeline") as mock:
        instance = mock.return_value
        instance.get_stats.return_value = {
            "total_chunks": 42,
            "model_ready": True,
            "vector_store_ready": True,
        }
        yield instance


# ===== 健康检查 =====

class TestHealthAPI:
    """健康检查端点测试"""

    @pytest.mark.asyncio
    async def test_health_check(self, client, mock_rag_pipeline, mock_translator, mock_answer_generator):
        """GET /api/health 返回 200"""
        with patch("app.routes.chat.get_pipeline", return_value=mock_rag_pipeline):
            with patch("app.routes.chat._get_nl2sql_pipeline") as mock_get:
                mock_nl2sql = MagicMock()
                mock_nl2sql.get_stats.return_value = {
                    "nl2sql_ready": True, "database_ready": True, "rag_ready": True
                }
                mock_get.return_value = mock_nl2sql
                resp = await client.get("/api/health")
                assert resp.status_code == 200
                data = resp.json()
                assert data["status"] == "ok"
                assert "version" in data

    @pytest.mark.asyncio
    async def test_health_check_no_nl2sql(self, client, mock_rag_pipeline):
        """NL2SQL 未配置时仍返回健康"""
        with patch("app.routes.chat.get_pipeline", return_value=mock_rag_pipeline):
            with patch("app.routes.chat._get_nl2sql_pipeline") as mock_get:
                mock_nl2sql = MagicMock()
                mock_nl2sql.get_stats.return_value = {
                    "nl2sql_ready": False, "database_ready": True, "rag_ready": True
                }
                mock_get.return_value = mock_nl2sql
                resp = await client.get("/api/health")
                assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_root_endpoint(self, client):
        """GET / 返回服务信息"""
        resp = await client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert "service" in data
        assert "version" in data


# ===== 聊天 API =====

class TestChatAPI:
    """聊天端点测试"""

    @pytest.mark.asyncio
    async def test_chat_basic(self, client):
        """POST /api/chat 返回回答"""
        with patch("app.routes.chat._get_nl2sql_pipeline") as mock_get:
            mock_pipeline = MagicMock()
            mock_pipeline.query.return_value = {
                "id": "test-id",
                "question": "测试问题",
                "answer": "测试回答",
                "sources": [],
                "conversation_id": "conv-1",
                "created_at": "2025-01-01T00:00:00",
                "response_time_ms": 100,
                "has_numeric_data": False,
                "chart_data": None,
                "sql": "SELECT 1",
                "sql_result": {"columns": ["col1"], "rows": [], "row_count": 0},
            }
            mock_get.return_value = mock_pipeline

            resp = await client.post(
                "/api/chat",
                json={"question": "测试问题"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["answer"] == "测试回答"
            assert data["question"] == "测试问题"
            assert data["conversation_id"] == "conv-1"

    @pytest.mark.asyncio
    async def test_chat_with_conversation_id(self, client):
        """POST /api/chat 携带 conversation_id"""
        with patch("app.routes.chat._get_nl2sql_pipeline") as mock_get:
            mock_pipeline = MagicMock()
            mock_pipeline.query.return_value = {
                "id": "test-id",
                "question": "测试问题",
                "answer": "回答",
                "sources": [],
                "conversation_id": "existing-conv",
                "created_at": "2025-01-01T00:00:00",
                "response_time_ms": 100,
                "has_numeric_data": False,
                "chart_data": None,
                "sql": "",
                "sql_result": None,
            }
            mock_get.return_value = mock_pipeline

            resp = await client.post(
                "/api/chat",
                json={"question": "测试问题", "conversation_id": "existing-conv"},
            )
            assert resp.status_code == 200
            assert resp.json()["conversation_id"] == "existing-conv"

    @pytest.mark.asyncio
    async def test_chat_empty_question(self, client):
        """空问题返回 422"""
        resp = await client.post("/api/chat", json={"question": ""})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_chat_stream_endpoint(self, client):
        """POST /api/chat/stream 返回 SSE 流"""
        with patch("app.routes.chat._get_nl2sql_pipeline") as mock_get:
            mock_pipeline = MagicMock()
            def stream_gen(q, conv_id=None):
                yield "这是"
                yield "流式"
                yield "回答"
            mock_pipeline.query_stream = stream_gen
            mock_pipeline._last_sql = "SELECT 1"
            mock_pipeline._last_sql_result = {"columns": ["a"], "rows": [], "row_count": 0}
            mock_pipeline._last_sources = []
            mock_pipeline._last_chart_data = None
            mock_pipeline._last_has_numeric_data = False
            mock_pipeline._last_response_time_ms = 50
            mock_get.return_value = mock_pipeline

            resp = await client.post(
                "/api/chat/stream",
                json={"question": "测试"},
            )
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers["content-type"]

    @pytest.mark.asyncio
    async def test_chat_agent_endpoint(self, client):
        """POST /api/chat/agent 返回回答"""
        with patch("app.routes.chat._get_nl2sql_pipeline") as mock_get:
            mock_pipeline = MagicMock()
            mock_pipeline.query_agent.return_value = {
                "id": "agent-id",
                "question": "agent测试",
                "answer": "agent回答",
                "sources": [],
                "conversation_id": "agent-conv",
                "created_at": "2025-01-01T00:00:00",
                "response_time_ms": 200,
                "has_numeric_data": False,
                "chart_data": None,
                "sql": "",
                "sql_result": None,
            }
            mock_get.return_value = mock_pipeline

            resp = await client.post(
                "/api/chat/agent",
                json={"question": "agent测试"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "agent回答" in data["answer"]

    @pytest.mark.asyncio
    async def test_chat_handles_exception(self, client):
        """异常时返回结构化错误"""
        with patch("app.routes.chat._get_nl2sql_pipeline") as mock_get:
            mock_pipeline = MagicMock()
            mock_pipeline.query.side_effect = ValueError("安全拦截: 危险操作")
            mock_get.return_value = mock_pipeline

            resp = await client.post(
                "/api/chat",
                json={"question": "危险操作"},
            )
            assert resp.status_code == 403
            data = resp.json()
            assert "detail" in data
            detail = data["detail"] if isinstance(data["detail"], dict) else json.loads(data["detail"])
            assert "SAFETY_VIOLATION" in detail.get("error_code", "")


# ===== 历史对话 API =====

class TestHistoryAPI:
    """历史对话端点测试"""

    @pytest.mark.asyncio
    async def test_get_history(self, client):
        """GET /api/history 返回对话列表"""
        with patch("app.routes.chat.get_conversation_store") as mock_get:
            mock_store = MagicMock()
            mock_store.list_all.return_value = [
                {"conversation_id": "c1", "last_message": "测试", "message_count": 2},
            ]
            mock_get.return_value = mock_store

            resp = await client.get("/api/history")
            assert resp.status_code == 200
            data = resp.json()
            assert "conversations" in data
            assert len(data["conversations"]) == 1

    @pytest.mark.asyncio
    async def test_get_conversation_found(self, client):
        """GET /api/history/{id} 返回对话"""
        with patch("app.routes.chat.get_conversation_store") as mock_get:
            mock_store = MagicMock()
            mock_store.get.return_value = {
                "conversation_id": "c1",
                "messages": [{"id": "m1", "question": "q1", "answer": "a1"}],
            }
            mock_get.return_value = mock_store

            resp = await client.get("/api/history/c1")
            assert resp.status_code == 200
            assert resp.json()["conversation_id"] == "c1"

    @pytest.mark.asyncio
    async def test_get_conversation_not_found(self, client):
        """不存在的对话返回 404"""
        with patch("app.routes.chat.get_conversation_store") as mock_get:
            mock_store = MagicMock()
            mock_store.get.return_value = None
            mock_get.return_value = mock_store

            resp = await client.get("/api/history/nonexistent")
            assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_conversation(self, client):
        """DELETE /api/history/{id} 删除对话"""
        with patch("app.routes.chat.get_conversation_store") as mock_get:
            mock_store = MagicMock()
            mock_store.delete.return_value = True
            mock_get.return_value = mock_store

            resp = await client.delete("/api/history/c1")
            assert resp.status_code == 200
            assert resp.json()["status"] == "deleted"

    @pytest.mark.asyncio
    async def test_delete_nonexistent_conversation(self, client):
        """删除不存在的对话返回 404"""
        with patch("app.routes.chat.get_conversation_store") as mock_get:
            mock_store = MagicMock()
            mock_store.delete.return_value = False
            mock_get.return_value = mock_store

            resp = await client.delete("/api/history/nonexistent")
            assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_history_empty(self, client):
        """无历史对话返回空列表"""
        with patch("app.routes.chat.get_conversation_store") as mock_get:
            mock_store = MagicMock()
            mock_store.list_all.return_value = []
            mock_get.return_value = mock_store

            resp = await client.get("/api/history")
            assert resp.status_code == 200
            assert resp.json()["conversations"] == []


# ===== 数据集 =====

class TestDatasetAPI:
    """数据集端点测试"""

    @pytest.mark.asyncio
    async def test_dataset_info(self, client, mock_rag_pipeline):
        """GET /api/dataset-info 返回数据集信息"""
        with patch("app.routes.chat.get_pipeline", return_value=mock_rag_pipeline):
            resp = await client.get("/api/dataset-info")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_chunks"] == 42

    @pytest.mark.asyncio
    async def test_rebuild_index(self, client, mock_rag_pipeline):
        """POST /api/rebuild-index 重建索引"""
        mock_rag_pipeline.build_index.return_value = 99
        with patch("app.routes.chat.get_pipeline", return_value=mock_rag_pipeline):
            resp = await client.post("/api/rebuild-index")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"
            assert data["chunks_created"] == 99


# ===== 知识库 API =====

class TestKnowledgeAPI:
    """知识库管理端点测试"""

    @pytest.mark.asyncio
    async def test_get_knowledge(self, client):
        """GET /api/knowledge/ 返回知识库"""
        with patch("app.routes.knowledge.load_knowledge") as mock_load:
            mock_load.return_value = {
                "question_sql_examples": [{"question": "q1", "sql": "s1"}],
                "synonym_mappings": [],
                "domain_mappings": [],
                "table_schemas": [],
            }
            resp = await client.get("/api/knowledge/")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["question_sql_examples"]) == 1

    @pytest.mark.asyncio
    async def test_get_knowledge_stats(self, client):
        """GET /api/knowledge/stats 返回统计"""
        with patch("app.routes.knowledge.get_stats") as mock_stats:
            mock_stats.return_value = {"total_examples": 28, "total_synonyms": 15, "total_domain_mappings": 10}
            resp = await client.get("/api/knowledge/stats")
            assert resp.status_code == 200
            assert resp.json()["total_examples"] == 28

    @pytest.mark.asyncio
    async def test_create_example(self, client):
        """POST /api/knowledge/examples 创建示例"""
        with patch("app.routes.knowledge.add_example") as mock_add:
            mock_add.return_value = {"status": "ok", "index": 0}
            resp = await client.post(
                "/api/knowledge/examples",
                json={"question": "q2", "sql": "s2", "tables": [], "tags": []},
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == "ok"

    @pytest.mark.asyncio
    async def test_delete_example(self, client):
        """DELETE /api/knowledge/examples/{index} 删除示例"""
        with patch("app.routes.knowledge.delete_example") as mock_del:
            mock_del.return_value = True
            resp = await client.delete("/api/knowledge/examples/0")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_delete_example_not_found(self, client):
        """删除不存在的示例返回 404"""
        with patch("app.routes.knowledge.delete_example") as mock_del:
            mock_del.return_value = False
            resp = await client.delete("/api/knowledge/examples/999")
            assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_create_synonym(self, client):
        """POST /api/knowledge/synonyms 创建同义词"""
        with patch("app.routes.knowledge.add_synonym") as mock_add:
            mock_add.return_value = {"status": "ok", "index": 0}
            resp = await client.post(
                "/api/knowledge/synonyms",
                json={"synonyms": ["手机", "移动电话"], "target_column": "品类", "table": "products"},
            )
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_create_domain_mapping(self, client):
        """POST /api/knowledge/domain-mappings 创建领域映射"""
        with patch("app.routes.knowledge.add_domain_mapping") as mock_add:
            mock_add.return_value = {"status": "ok", "index": 0}
            resp = await client.post(
                "/api/knowledge/domain-mappings",
                json={"term": "巨头", "mapping": "企业营收 > 1000", "table": "companies"},
            )
            assert resp.status_code == 200


# ===== 反馈 API =====

class TestFeedbackAPI:
    """反馈端点测试"""

    FEEDBACK_PATH = "backend/data/feedback.json"

    @pytest.mark.asyncio
    async def test_submit_feedback_like(self, client):
        """POST /api/feedback 提交点赞"""
        test_data = {"message_id": "msg-1", "rating": "like"}
        with patch("app.routes.feedback._load_feedback", return_value=[]):
            with patch("app.routes.feedback._save_feedback") as mock_save:
                resp = await client.post("/api/feedback", json=test_data)
                assert resp.status_code == 200
                assert resp.json()["status"] == "ok"

    @pytest.mark.asyncio
    async def test_submit_feedback_dislike(self, client):
        """POST /api/feedback 提交点踩"""
        test_data = {"message_id": "msg-2", "rating": "dislike", "comment": "回答不准确"}
        with patch("app.routes.feedback._load_feedback", return_value=[]):
            with patch("app.routes.feedback._save_feedback") as mock_save:
                resp = await client.post("/api/feedback", json=test_data)
                assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_submit_feedback_invalid_rating(self, client):
        """无效 rating 返回 400"""
        resp = await client.post(
            "/api/feedback",
            json={"message_id": "msg-3", "rating": "invalid"},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_feedback_stats(self, client):
        """GET /api/feedback/stats 返回统计"""
        mock_data = [
            {"message_id": "m1", "rating": "like", "timestamp": "2025-01-01"},
            {"message_id": "m2", "rating": "dislike", "timestamp": "2025-01-02"},
            {"message_id": "m3", "rating": "like", "timestamp": "2025-01-03"},
        ]
        with patch("app.routes.feedback._load_feedback", return_value=mock_data):
            resp = await client.get("/api/feedback/stats")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 3
            assert data["likes"] == 2
            assert data["dislikes"] == 1
            assert data["like_rate"] == 66.7

    @pytest.mark.asyncio
    async def test_feedback_stats_empty(self, client):
        """空反馈数据返回零值"""
        with patch("app.routes.feedback._load_feedback", return_value=[]):
            resp = await client.get("/api/feedback/stats")
            assert resp.status_code == 200
            assert resp.json()["total"] == 0
            assert resp.json()["like_rate"] == 0


# ===== 看板 API =====

class TestDashboardAPI:
    """看板端点测试"""

    @pytest.mark.asyncio
    async def test_dashboard_overview(self, client):
        """GET /api/dashboard/overview 返回看板数据"""
        mock_stats = {
            "total_revenue": 100000,
            "total_orders": 300,
            "total_customers": 100,
            "refund_rate": 5.2,
            "category_revenue": {"labels": ["电子", "服装"], "data": [60000, 40000]},
            "monthly_trend": {"labels": ["1月", "2月"], "data": [5000, 6000]},
            "province_distribution": {"labels": ["广东", "浙江"], "data": [55, 45]},
        }
        with patch("app.routes.analytics.get_overview_stats", return_value=mock_stats):
            resp = await client.get("/api/dashboard/overview")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_revenue"] == 100000
            assert data["total_orders"] == 300


# ===== 导出 API =====

class TestExportAPI:
    """导出端点测试"""

    @pytest.mark.asyncio
    async def test_export_csv(self, client):
        """GET /api/export 导出 CSV"""
        mock_conv = {
            "conversation_id": "c1",
            "messages": [{
                "id": "m1",
                "sql_result": {
                    "columns": ["品类", "销售额"],
                    "rows": [{"品类": "电子", "销售额": 100}],
                },
            }],
        }
        with patch("app.routes.export.get_conversation_store") as mock_get:
            mock_store = MagicMock()
            mock_store.get.return_value = mock_conv
            mock_get.return_value = mock_store

            resp = await client.get("/api/export", params={
                "conversation_id": "c1", "message_id": "m1", "format": "csv",
            })
            assert resp.status_code == 200
            assert resp.headers["content-type"] == "text/csv; charset=utf-8-sig"
            assert "品类" in resp.text

    @pytest.mark.asyncio
    async def test_export_conversation_not_found(self, client):
        """不存在的对话返回 404"""
        with patch("app.routes.export.get_conversation_store") as mock_get:
            mock_store = MagicMock()
            mock_store.get.return_value = None
            mock_get.return_value = mock_store

            resp = await client.get("/api/export", params={
                "conversation_id": "nonexistent", "message_id": "m1",
            })
            assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_export_message_not_found(self, client):
        """不存在的消息返回 404"""
        mock_conv = {"conversation_id": "c1", "messages": []}
        with patch("app.routes.export.get_conversation_store") as mock_get:
            mock_store = MagicMock()
            mock_store.get.return_value = mock_conv
            mock_get.return_value = mock_store

            resp = await client.get("/api/export", params={
                "conversation_id": "c1", "message_id": "nonexistent",
            })
            assert resp.status_code == 404


# ===== 文件上传 API =====

class TestUploadAPI:
    """文件上传端点测试"""

    @pytest.mark.asyncio
    async def test_upload_csv(self, client):
        """POST /api/upload 上传 CSV 文件"""
        csv_content = b"col1,col2\nval1,val2\n"
        with patch("app.routes.upload.validate_file", return_value=None):
            with patch("app.routes.upload.save_uploaded_file", return_value="/tmp/test.csv"):
                with patch("app.routes.upload.import_to_database", return_value={
                    "row_count": 1, "columns": ["col1", "col2"],
                }):
                    resp = await client.post(
                        "/api/upload",
                        files={"file": ("test.csv", csv_content, "text/csv")},
                    )
                    assert resp.status_code == 200
                    data = resp.json()
                    assert data["status"] == "ok"
                    assert data["row_count"] == 1

    @pytest.mark.asyncio
    async def test_upload_invalid_file(self, client):
        """不支持的文件类型返回 400"""
        with patch("app.routes.upload.validate_file", return_value="不支持的文件类型"):
            resp = await client.post(
                "/api/upload",
                files={"file": ("test.exe", b"data", "application/octet-stream")},
            )
            assert resp.status_code == 400


# ===== 数据库安全 =====

class TestSQLSafety:
    """SQL 安全校验测试（复用现有测试的扩展）"""

    def test_safety_blocks_drop(self):
        from app.nl2sql.database import _validate_sql_safety
        import pytest
        with pytest.raises(ValueError, match="安全拦截"):
            _validate_sql_safety("DROP TABLE orders")

    def test_safety_blocks_multi_statement(self):
        from app.nl2sql.database import _validate_sql_safety
        with pytest.raises(ValueError, match="安全拦截"):
            _validate_sql_safety("SELECT 1; DROP TABLE orders")

    def test_safety_allows_complex_select(self):
        from app.nl2sql.database import _validate_sql_safety
        _validate_sql_safety("WITH t AS (SELECT * FROM [orders]) SELECT * FROM t WHERE [金额] > 100")
