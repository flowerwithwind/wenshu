import pytest
import os
import sys
import tempfile
import sqlite3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# 覆盖数据库路径，使用临时文件
TEST_DB_PATH = os.path.join(tempfile.gettempdir(), "test_knowledge.db")


@pytest.fixture
def test_db():
    """创建测试数据库"""
    from app.nl2sql.database import init_database, DB_PATH, DATASET_DIR
    # 用临时路径
    import app.nl2sql.database as db_module
    original_db = db_module.DB_PATH
    db_module.DB_PATH = TEST_DB_PATH

    # 初始化数据库
    conn = init_database(TEST_DB_PATH)
    yield conn
    conn.close()
    # 清理
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    db_module.DB_PATH = original_db


@pytest.fixture
def db_connection():
    """获取数据库连接"""
    from app.nl2sql.database import get_connection
    import app.nl2sql.database as db_module
    original_db = db_module.DB_PATH
    db_module.DB_PATH = TEST_DB_PATH

    # 初始化
    from app.nl2sql.database import init_database
    conn = init_database(TEST_DB_PATH)

    yield conn
    conn.close()
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    db_module.DB_PATH = original_db