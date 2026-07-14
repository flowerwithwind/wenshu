"""
全量清理并重建 Chroma 向量索引（推荐：先停掉后端再运行）。

用法:
  conda activate wenshu
  cd backend
  python scripts/rebuild_index.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import CHROMA_PERSIST_DIR, DATASET_DIR
from app.rag.pipeline import get_pipeline
import app.rag.pipeline as rp


def main() -> None:
    print("=" * 50)
    print("全量重建向量索引（清空后写入）")
    print("=" * 50)
    print(f"DATASET_DIR = {DATASET_DIR}")
    print(f"CHROMA_DIR  = {CHROMA_PERSIST_DIR}")
    print(f"dataset ok  = {Path(DATASET_DIR).exists()}")

    # 重置单例，确保干净加载
    rp._pipeline = None

    pipeline = get_pipeline()
    print(f"[..] 重建前 ready={pipeline.vsm.is_ready()} "
          f"count={pipeline.vsm.get_collection_stats().get('total', 0)}")

    # 强制清空
    pipeline.vsm.reset_corrupt_index()
    # 再 build（内部 create_from_documents 也会清空）
    count = pipeline.build_index()
    stats = pipeline.get_stats()
    actual = stats.get("total_chunks", 0)

    print("-" * 50)
    print(f"chunks_written     = {count}")
    print(f"chunks_in_collection = {actual}")
    print(f"vector_store_ready = {stats.get('vector_store_ready')}")
    print(f"chroma_exists      = {Path(CHROMA_PERSIST_DIR).exists()}")
    print("=" * 50)

    if not stats.get("vector_store_ready") or actual <= 0:
        print("FAILED: 索引未就绪")
        sys.exit(1)
    if actual > count * 1.1 and count > 0:
        print(f"WARNING: 集合数量({actual}) > 写入量({count})，可能仍有重复")
        sys.exit(2)

    print("SUCCESS: 无重复累计")
    sys.exit(0)


if __name__ == "__main__":
    main()
