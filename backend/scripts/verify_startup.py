"""验证冷启动：向量库加载 + FastAPI lifespan + /api/health"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> None:
    print("=" * 50)
    print("验证冷启动")
    print("=" * 50)

    # 1. 干净进程加载向量库
    import app.rag.pipeline as rp
    import app.nl2sql.pipeline as np

    rp._pipeline = None
    np._pipeline = None

    from app.rag.pipeline import get_pipeline
    from app.nl2sql.pipeline import get_nl2sql_pipeline
    from app.nl2sql.database import init_database, is_database_ready

    print("[1] SQLite...")
    init_database()
    print(f"    database_ready={is_database_ready()}")

    print("[2] RAG load...")
    rag = get_pipeline()
    rag_stats = rag.get_stats()
    print(f"    stats={rag_stats}")
    assert rag_stats.get("vector_store_ready"), "向量库未就绪"
    assert rag_stats.get("total_chunks", 0) > 0, "文档块数为 0"

    print("[3] NL2SQL...")
    nl2sql = get_nl2sql_pipeline(rag_retriever=rag.retriever)
    nstats = nl2sql.get_stats()
    print(f"    stats={nstats}")
    assert nstats.get("database_ready"), "数据库未就绪"
    assert nstats.get("rag_ready"), "RAG 应就绪（向量库可用）"

    print("[4] FastAPI TestClient /api/health ...")
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        resp = client.get("/api/health")
        print(f"    status={resp.status_code} body={resp.json()}")
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("status") == "ok"
        vs = body.get("vector_store", "")
        assert "就绪" in vs or "块" in vs, f"unexpected vector_store: {vs}"

    print("=" * 50)
    print("STARTUP VERIFY SUCCESS")
    print("=" * 50)


if __name__ == "__main__":
    main()
