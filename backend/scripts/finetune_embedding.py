"""
Embedding 模型微调脚本

基于 sentence-transformers 的 MultipleNegativesRankingLoss，
对 BAAI/bge-large-zh-v1.5 进行领域自适应微调。

用法:
    conda activate wenshu
    cd backend
    python scripts/finetune_embedding.py

输出: data/models/finetuned-bge/
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

TRAIN_DATA_PATH = BACKEND_ROOT / "data" / "training" / "train_triplets.json"
OUTPUT_DIR = BACKEND_ROOT / "data" / "models" / "finetuned-bge"
BASE_MODEL = "BAAI/bge-large-zh-v1.5"


def load_triplets(path: str) -> list[dict]:
    """加载三元组训练数据"""
    if not os.path.exists(path):
        print(f"[ERROR] 训练数据不存在: {path}")
        print("请先运行: python scripts/prepare_training_data.py")
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"加载 {len(data)} 条训练三元组")
    return data


def train():
    """执行微调训练"""
    triplets = load_triplets(str(TRAIN_DATA_PATH))
    if not triplets:
        return

    try:
        from sentence_transformers import (
            SentenceTransformer,
            losses,
            InputExample,
            evaluation,
        )
        from torch.utils.data import DataLoader
    except ImportError as e:
        print(f"[ERROR] 缺少依赖: {e}")
        print("请安装: pip install sentence-transformers torch")
        return

    # 加载基座模型
    print(f"加载基座模型: {BASE_MODEL}")
    model = SentenceTransformer(BASE_MODEL)

    # 构造训练样本
    train_samples = []
    for t in triplets:
        train_samples.append(
            InputExample(
                texts=[t["query"], t["positive"], t["negative"]]
            )
        )

    # DataLoader
    batch_size = 8
    train_dataloader = DataLoader(train_samples, shuffle=True, batch_size=batch_size)

    # 损失函数：MultipleNegativesRankingLoss
    # 让 query 和 positive 的距离近，和 negative 的距离远
    train_loss = losses.MultipleNegativesRankingLoss(model)

    # 训练参数
    num_epochs = 3
    warmup_steps = int(len(train_dataloader) * num_epochs * 0.1)

    print(f"开始训练: epochs={num_epochs}, batch_size={batch_size}, warmup={warmup_steps}")
    print(f"训练样本数: {len(train_samples)}")

    model.fit(
        train_objectives=[(train_dataloader, train_loss)],
        epochs=num_epochs,
        warmup_steps=warmup_steps,
        output_path=str(OUTPUT_DIR),
        show_progress_bar=True,
        checkpoint_save_steps=len(train_dataloader),  # 每个 epoch 保存一次
        checkpoint_path=str(OUTPUT_DIR / "checkpoints"),
    )

    print(f"训练完成！模型已保存到: {OUTPUT_DIR}")
    print(f"可用配置: EMBEDDING_MODEL={OUTPUT_DIR}")


def quick_test():
    """快速测试微调后的模型效果"""
    model_path = str(OUTPUT_DIR)
    if not os.path.exists(model_path):
        print(f"[INFO] 微调模型不存在: {model_path}")
        print("请先运行训练: python scripts/finetune_embedding.py")
        return

    from sentence_transformers import SentenceTransformer, util

    print(f"加载微调模型: {model_path}")
    model = SentenceTransformer(model_path)

    # 测试用例
    queries = [
        "上个月销量最高的产品",
        "库存不足的商品有哪些",
        "客户的消费金额排名",
    ]

    candidates = [
        "查询产品销量数据",
        "分析库存管理",
        "客户价值分析",
        "SQL查询优化技巧",
        "数据库表结构说明",
    ]

    query_emb = model.encode(queries, normalize_embeddings=True)
    cand_emb = model.encode(candidates, normalize_embeddings=True)

    print("\n=== 微调模型相似度测试 ===")
    for i, q in enumerate(queries):
        scores = util.cos_sim(query_emb[i], cand_emb)[0]
        top_idx = scores.argmax().item()
        print(f"  Query: {q}")
        print(f"  Top1: {candidates[top_idx]} (score={scores[top_idx]:.4f})")
        print()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", action="store_true", help="执行训练")
    parser.add_argument("--test", action="store_true", help="测试微调模型")
    parser.add_argument("--all", action="store_true", help="先训练后测试")
    args = parser.parse_args()

    if args.all or (not args.train and not args.test):
        train()
        quick_test()
    elif args.train:
        train()
    elif args.test:
        quick_test()
