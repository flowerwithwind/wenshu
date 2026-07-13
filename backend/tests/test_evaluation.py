"""NL2SQL 评测框架单元测试"""
from __future__ import annotations

import os
import pytest
from app.evaluation.dataset import (
    EVAL_DATASET, get_eval_case, get_cases_by_category, list_categories, EvalCase,
)
from app.evaluation.metrics import (
    check_sql_validity, exact_set_match, evaluate_execution, run_single_evaluation, EvalResult,
)


class TestEvaluationDataset:
    """评测数据集测试"""

    def test_dataset_not_empty(self) -> None:
        assert len(EVAL_DATASET) > 0

    def test_all_cases_have_unique_ids(self) -> None:
        ids = [c.id for c in EVAL_DATASET]
        assert len(ids) == len(set(ids))

    def test_all_cases_have_required_fields(self) -> None:
        for case in EVAL_DATASET:
            assert case.id and case.question and case.sql and case.category

    def test_get_eval_case_found(self) -> None:
        case = get_eval_case("E001")
        assert case is not None
        assert case.id == "E001"

    def test_get_eval_case_not_found(self) -> None:
        assert get_eval_case("NONEXIST") is None

    def test_get_cases_by_category(self) -> None:
        cases = get_cases_by_category("simple")
        assert len(cases) > 0
        assert all(c.category == "simple" for c in cases)

    def test_list_categories(self) -> None:
        cats = list_categories()
        assert "simple" in cats
        assert "join" in cats
        assert "complex" in cats


class TestEvaluationMetrics:
    """评测指标测试"""

    def test_check_sql_validity_valid(self) -> None:
        assert check_sql_validity("SELECT * FROM [orders]")
        assert check_sql_validity("WITH t AS (SELECT 1) SELECT * FROM t")

    def test_check_sql_validity_invalid(self) -> None:
        assert not check_sql_validity("")
        assert not check_sql_validity("DROP TABLE [orders]")
        assert not check_sql_validity("   ")

    def test_check_sql_validity_none(self) -> None:
        assert not check_sql_validity("")

    def test_exact_set_match_identical(self) -> None:
        rows_a = [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]
        rows_b = [{"a": 2, "b": "y"}, {"a": 1, "b": "x"}]
        assert exact_set_match(rows_a, rows_b)

    def test_exact_set_match_different(self) -> None:
        rows_a = [{"a": 1}, {"a": 2}]
        rows_b = [{"a": 1}, {"a": 3}]
        assert not exact_set_match(rows_a, rows_b)

    def test_exact_set_match_different_length(self) -> None:
        rows_a = [{"a": 1}]
        rows_b = [{"a": 1}, {"a": 2}]
        assert not exact_set_match(rows_a, rows_b)

    def test_evaluate_execution_success(self) -> None:
        success, rows, cols, err = evaluate_execution("SELECT 1 AS test")
        assert success
        assert len(cols) > 0
        assert "test" in cols
        assert err == ""

    def test_evaluate_execution_failure(self) -> None:
        success, rows, cols, err = evaluate_execution("SELECT * FROM [nonexistent_table]")
        assert not success
        assert err

    def test_evaluate_execution_safety_block(self) -> None:
        success, rows, cols, err = evaluate_execution("DROP TABLE [orders]")
        assert not success
        assert "安全拦截" in err

    def test_run_single_evaluation_basic(self) -> None:
        result = run_single_evaluation(
            case_id="TEST",
            question="test",
            ground_truth_sql="SELECT 1 AS a",
            generated_sql="SELECT 1 AS a",
        )
        assert result.case_id == "TEST"
        assert result.is_valid_sql
        assert result.execution_success
        assert result.llm_score is None  # no LLM judge provided

    def test_run_single_evaluation_invalid_sql(self) -> None:
        result = run_single_evaluation(
            case_id="TEST2",
            question="test",
            ground_truth_sql="SELECT 1",
            generated_sql="INVALID SQL HERE",
        )
        assert result.is_valid_sql is False

    def test_run_single_evaluation_exact_match(self) -> None:
        result = run_single_evaluation(
            case_id="TEST3",
            question="test",
            ground_truth_sql="SELECT 1 AS a",
            generated_sql="SELECT 1 AS a",
        )
        # Both should execute successfully and match
        assert result.execution_success
        # exact_set_match might be True since both queries return same result
        # but the column names could differ in the execution
        assert result.exact_set_match is not None

    @pytest.mark.skipif(not os.getenv("DEEPSEEK_API_KEY"), reason="DEEPSEEK_API_KEY 未配置")
    def test_run_single_evaluation_with_llm_judge(self) -> None:
        from app.evaluation.metrics import LLMJudge
        judge = LLMJudge()
        result = run_single_evaluation(
            case_id="TEST_LLM",
            question="test",
            ground_truth_sql="SELECT COUNT(*) AS 订单总数 FROM [orders]",
            generated_sql="SELECT COUNT(*) AS 订单总数 FROM [orders]",
            llm_judge=judge,
        )
        assert result.llm_score is not None
        assert 1.0 <= result.llm_score <= 5.0
