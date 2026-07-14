# backend/data 目录约定

本目录存放**演示数据集**与**运行时生成数据**。提交仓库时只保留可复现演示所需的静态文件。

## 应纳入版本库

| 路径 | 说明 |
|------|------|
| `datasets/*.csv` | 电商演示表（customers / products / orders / …） |
| `datasets/nl2sql_knowledge.json` | Few-shot、同义词、领域映射、表语义 |
| `datasets/data_readme.txt` | 数据集说明 |
| `README.md` | 本说明 |

## 本地运行时生成（已 gitignore）

| 路径 | 说明 |
|------|------|
| `chroma_db/` | Chroma 向量索引（`python scripts/preprocess.py` 或重建索引生成） |
| `knowledge.db` | 从 CSV 导入的内置 SQLite |
| `conversations.db` / `conversations/` | 对话历史 |
| `llm_settings.json` | 前端/API 保存的模型配置（可覆盖 `.env`） |
| `datasources.json` | 外部数据源注册信息 |
| `sql_audit.jsonl` | SQL 审计日志 |
| `.ds_secret_key` | 数据源密码加密密钥 |

## 启动前

```bash
cd backend
conda activate wenshu
python scripts/preprocess.py   # 生成 knowledge.db + chroma_db（首次或数据变更后）
```

## 注意

- 勿再创建 `data/data/` 嵌套路径；相对路径一律以 `backend/` 为根（见 `app/config.py`）。
- 密钥只放 `backend/.env` 或通过「系统设置」写入 `llm_settings.json`，不要提交。
