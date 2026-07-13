"""SQL 自纠错器单元测试"""
from __future__ import annotations

import os
import pytest
from app.nl2sql.corrector import SQLCorrector


class TestSQLCorrector:
    """SQL 自纠错器基础功能测试"""

    @pytest.fixture
    def corrector(self) -> SQLCorrector:
        return SQLCorrector(max_retries=3)

    def test_initial_state(self, corrector: SQLCorrector) -> None:
        assert corrector.attempt_count == 0
        assert not corrector.exhausted

    def test_exhausted_after_max_retries(self, corrector: SQLCorrector) -> None:
        for _ in range(3):
            assert not corrector.exhausted
            corrector._attempt_count += 1
        assert corrector.exhausted

    def test_reset(self, corrector: SQLCorrector) -> None:
        corrector._attempt_count = 2
        corrector.reset()
        assert corrector.attempt_count == 0
        assert not corrector.exhausted

    def test_clean_sql_removes_markdown(self, corrector: SQLCorrector) -> None:
        cleaned = corrector._clean_sql("```sql\nSELECT * FROM [orders]\n```")
        assert cleaned == "SELECT * FROM [orders]"

    def test_clean_sql_no_change(self, corrector: SQLCorrector) -> None:
        sql = "SELECT * FROM [orders]"
        assert corrector._clean_sql(sql) == sql

    def test_correct_syntax_error(self) -> None:
        """修正语法错误（需要 DEEPSEEK_API_KEY）"""
        if not os.getenv("DEEPSEEK_API_KEY"):
            pytest.skip("DEEPSEEK_API_KEY 未配置")

        corrector = SQLCorrector(max_retries=2)
        schema = "表 [orders]: 订单ID(INTEGER), 日期(TEXT), 订单金额_元(REAL)"
        sql = "SELET * FROM [orders]"  # 故意拼错 SELECT

        corrected = corrector.correct(
            question="查询所有订单",
            sql=sql,
            error='near "SELET": syntax error',
            schema=schema,
        )
        assert corrected
        assert corrected.strip().upper().startswith("SELECT")

    def test_correct_column_name(self) -> None:
        """修正列名错误"""
        if not os.getenv("DEEPSEEK_API_KEY"):
            pytest.skip("DEEPSEEK_API_KEY 未配置")

        corrector = SQLCorrector(max_retries=2)
        schema = (
            "表 [orders]: 订单ID(INTEGER), 日期(TEXT), 订单金额_元(REAL)\n"
            "表 [customers]: 客户ID(INTEGER), 姓名(TEXT), 会员等级(TEXT)"
        )
        # "金额" 应该修正为 "订单金额_元"
        sql = "SELECT SUM([金额]) FROM [orders]"

        corrected = corrector.correct(
            question="查询总金额",
            sql=sql,
            error='no such column: 金额',
            schema=schema,
        )
        assert corrected
        assert corrected.strip().upper().startswith("SELECT")
        # 修正后的 SQL 应该包含正确的列名
        assert "金额_元" in corrected or "金额" not in corrected

    def test_correct_with_history(self) -> None:
        """带历史记录的修正"""
        if not os.getenv("DEEPSEEK_API_KEY"):
            pytest.skip("DEEPSEEK_API_KEY 未配置")

        corrector = SQLCorrector(max_retries=3)
        schema = "表 [orders]: 订单ID(INTEGER), 订单金额_元(REAL)"
        history = "尝试1: SQL=SELET * FROM [orders]\n  错误=near 'SELET': syntax error\n"

        corrected = corrector.correct(
            question="查询所有订单",
            sql="SELET * FROM [orders]",
            error='near "SELET": syntax error',
            schema=schema,
            history=history,
        )
        assert corrected
        assert corrected.strip().upper().startswith("SELECT")
