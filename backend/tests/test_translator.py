"""NL2SQL 翻译器单元测试"""
import pytest
import os
from app.nl2sql.translator import NL2SQLTranslator, AnswerGenerator


class TestNL2SQLTranslator:
    """NL2SQL 翻译器测试"""

    @pytest.fixture
    def translator(self):
        """纯单元测试用：延迟初始化 LLM，不要求网络"""
        return NL2SQLTranslator()

    @pytest.fixture
    def live_translator(self):
        """需要真实 API 的用例"""
        if not os.getenv("DEEPSEEK_API_KEY"):
            pytest.skip("DEEPSEEK_API_KEY 未配置")
        return NL2SQLTranslator()

    def test_translate_simple_question(self, live_translator):
        """简单聚合查询"""
        schema = "表 [orders]: 订单ID, 日期, 订单金额_元"
        sql = live_translator.translate("订单总数是多少", schema)
        assert sql
        assert "SELECT" in sql.upper()
        assert "COUNT" in sql.upper()

    def test_translate_join_question(self, live_translator):
        """JOIN 查询"""
        schema = "表 [orders]: 订单ID, 客户ID\n表 [customers]: 客户ID, 姓名"
        sql = live_translator.translate("每个客户的订单数", schema)
        assert sql
        assert "SELECT" in sql.upper()

    def test_translate_returns_only_sql(self, live_translator):
        """返回纯净 SQL"""
        schema = "表 [orders]: 订单ID, 日期, 订单金额_元"
        sql = live_translator.translate("订单总数", schema)
        assert sql
        assert not sql.startswith("```")
        assert not sql.endswith("```")

    def test_invalid_sql_detected(self, translator):
        """CANNOT_TRANSLATE 被识别"""
        assert not translator._is_valid_sql("CANNOT_TRANSLATE")
        assert not translator._is_valid_sql("")
        assert not translator._is_valid_sql("无法翻译")

    def test_sql_is_cleaned(self, translator):
        """Markdown ``` 包裹被清理"""
        result = translator._clean_sql("```sql\nSELECT * FROM [orders]\n```")
        assert result == "SELECT * FROM [orders]"

        result = translator._clean_sql("```\nSELECT 1\n```")
        assert result == "SELECT 1"

        result = translator._clean_sql("SELECT 1")
        assert result == "SELECT 1"

    def test_is_valid_sql_rejects_non_select(self, translator):
        """非 SELECT 语句被拒绝"""
        assert not translator._is_valid_sql("INSERT INTO orders VALUES (1)")
        assert not translator._is_valid_sql("DELETE FROM orders")
        assert translator._is_valid_sql("SELECT * FROM [orders]")

    def test_extract_examples_from_context(self, translator):
        """从 RAG 上下文提取示例"""
        context = """【示例问题】销售额最高的品类
【对应SQL】SELECT ... FROM orders
【领域术语】...
【示例问题】订单趋势
【对应SQL】SELECT ... FROM orders"""
        result = translator._extract_examples_from_context(context)
        assert "销售额最高的品类" in result
        assert "订单趋势" in result


class TestAnswerGenerator:
    """回答生成器测试"""

    def test_extract_chart_data(self):
        """解析 chart_data 代码块（无网络）"""
        gen = AnswerGenerator()
        text = '分析完成\n```chart_data\n{"type": "bar", "labels": ["A"], "datasets": [{"data": [1]}]}\n```'
        chart = gen._extract_chart_data(text)
        assert chart is not None
        assert chart["type"] == "bar"

    def test_clean_chart_markdown(self):
        gen = AnswerGenerator()
        text = '前文\n```chart_data\n{"type": "pie"}\n```\n后文'
        cleaned = gen._clean_chart_markdown(text)
        assert "chart_data" not in cleaned
        assert "前文" in cleaned

    def test_generate_with_data(self):
        """有数据时生成回答（需 API）"""
        if not os.getenv("DEEPSEEK_API_KEY"):
            pytest.skip("DEEPSEEK_API_KEY 未配置")
        generator = AnswerGenerator()
        result = generator.generate(
            question="销售额最高的品类",
            sql="SELECT 品类, SUM(订单金额_元) FROM orders GROUP BY 品类",
            columns=["品类", "销售额"],
            rows=[{"品类": "电子", "销售额": 10000}],
        )
        assert "answer" in result
        assert result["answer"]

    def test_generate_empty_result(self):
        """空结果时生成回答（需 API）"""
        if not os.getenv("DEEPSEEK_API_KEY"):
            pytest.skip("DEEPSEEK_API_KEY 未配置")
        generator = AnswerGenerator()
        result = generator.generate(
            question="不存在的数据",
            sql="SELECT * FROM orders WHERE 1=0",
            columns=["订单ID"],
            rows=[],
        )
        assert "answer" in result
        assert result["answer"]
