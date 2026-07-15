import pytest
import os
import sys
import tempfile
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def test_db():
    """创建隔离的临时测试数据库，并覆盖模块级 DB_PATH。"""
    import app.nl2sql.database as db_module
    from app.nl2sql.database import init_database

    original_db = db_module.DB_PATH
    test_db_path = os.path.join(
        tempfile.gettempdir(), f"test_knowledge_{uuid.uuid4().hex}.db"
    )
    db_module.DB_PATH = test_db_path

    conn = init_database(test_db_path)
    try:
        yield conn
    finally:
        try:
            conn.close()
        except Exception:
            pass
        if os.path.exists(test_db_path):
            try:
                os.remove(test_db_path)
            except OSError:
                pass
        db_module.DB_PATH = original_db


@pytest.fixture
def db_connection(test_db):
    """与 test_db 等价，保留旧 fixture 名称兼容。"""
    yield test_db
