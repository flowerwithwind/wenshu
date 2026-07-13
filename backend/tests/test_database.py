"""数据库模块单元测试"""
import pytest
import os
import tempfile
from app.nl2sql.database import (
    execute_sql,
    get_schema_info,
    is_database_ready,
    _validate_sql_safety,
    init_database,
)


class TestSQLSafety:
    """SQL 安全校验测试"""

    def test_sql_safety_allows_select(self):
        """SELECT 正常通过"""
        _validate_sql_safety("SELECT * FROM [orders]")
        _validate_sql_safety("SELECT COUNT(*) FROM [orders]")
        _validate_sql_safety("select * from [orders]")

    def test_sql_safety_allows_with_cte(self):
        """WITH CTE SELECT 正常通过"""
        _validate_sql_safety("WITH t AS (SELECT * FROM [orders]) SELECT * FROM t")

    def test_sql_safety_blocks_drop(self):
        """DROP 被拦截"""
        with pytest.raises(ValueError, match="安全拦截"):
            _validate_sql_safety("DROP TABLE orders")

    def test_sql_safety_blocks_delete(self):
        """DELETE 被拦截"""
        with pytest.raises(ValueError, match="安全拦截"):
            _validate_sql_safety("DELETE FROM orders")

    def test_sql_safety_blocks_insert(self):
        """INSERT 被拦截"""
        with pytest.raises(ValueError, match="安全拦截"):
            _validate_sql_safety("INSERT INTO orders VALUES (1)")

    def test_sql_safety_blocks_update(self):
        """UPDATE 被拦截"""
        with pytest.raises(ValueError, match="安全拦截"):
            _validate_sql_safety("UPDATE orders SET status='done'")

    def test_sql_safety_blocks_create(self):
        """CREATE 被拦截"""
        with pytest.raises(ValueError, match="安全拦截"):
            _validate_sql_safety("CREATE TABLE test (id INT)")

    def test_sql_safety_blocks_alter(self):
        """ALTER 被拦截"""
        with pytest.raises(ValueError, match="安全拦截"):
            _validate_sql_safety("ALTER TABLE orders ADD COLUMN x INT")


class TestDatabaseOperations:
    """数据库操作测试"""

    def test_init_database_creates_tables(self, test_db):
        """验证所有表都被创建"""
        cursor = test_db.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        expected_tables = ["customers", "products", "orders", "monthly_targets", "refunds"]
        for table in expected_tables:
            assert table in tables, f"表 {table} 未被创建"

    def test_execute_select_success(self, test_db):
        """正常 SELECT 查询"""
        rows, columns = execute_sql("SELECT COUNT(*) AS cnt FROM [orders]")
        assert len(rows) > 0
        assert columns == ["cnt"]
        assert rows[0]["cnt"] > 0

    def test_execute_sql_blocks_dangerous(self, test_db):
        """execute_sql 拦截危险操作"""
        with pytest.raises(ValueError, match="安全拦截"):
            execute_sql("DROP TABLE orders")

    def test_get_schema_info_returns_all_tables(self, test_db):
        """Schema 信息包含所有表"""
        schema = get_schema_info()
        assert "customers" in schema
        assert "products" in schema
        assert "orders" in schema
        assert "monthly_targets" in schema
        assert "refunds" in schema

    def test_is_database_ready(self):
        """数据库就绪检查"""
        assert is_database_ready() is True

    def test_execute_sql_with_join(self, test_db):
        """JOIN 查询"""
        sql = """
            SELECT [o].[订单ID], [c].[姓名]
            FROM [orders] [o]
            JOIN [customers] [c] ON [o].[客户ID] = [c].[客户ID]
            LIMIT 5
        """
        rows, columns = execute_sql(sql)
        assert len(rows) > 0
        assert "订单ID" in columns
        assert "姓名" in columns

    def test_execute_sql_empty_result(self, test_db):
        """空结果查询"""
        rows, columns = execute_sql(
            "SELECT * FROM [orders] WHERE [订单状态] = 'NONEXISTENT'"
        )
        assert len(rows) == 0