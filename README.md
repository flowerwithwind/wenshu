# 智能问数系统 (SmartQA)

基于 **NL2SQL + RAG + ReAct Agent** 的智能数据问答系统。支持用自然语言查询电商结构化数据，自动生成 SQL、执行分析并可视化。

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | FastAPI · LangChain · SQLite · ChromaDB · sentence-transformers |
| 前端 | Vue 3 · Pinia · Chart.js · Markdown |
| 模型 | DeepSeek（默认，OpenAI 兼容）；可切换 OpenAI / Anthropic |
| 嵌入 | `BAAI/bge-large-zh-v1.5` |
| 可观测 | loguru · OpenTelemetry · 限流 |
| 环境 | **conda 环境 `wenshu`** · Docker Compose 可选 |

## 架构

```
用户提问
  ├─ Pipeline：意图 → 多轮上下文 → RAG 辅助 → NL2SQL → 执行(+自纠错) → 回答/图表
  │              └ 失败回退 RAG
  └─ Agent：ReAct + tools（get_schema / sample / execute_sql / search_knowledge）
```

数据：电商 5 表星型模型

| 表 | 说明 |
|---|---|
| customers | 客户维度 ~100 人 |
| products | 商品维度 ~40 款 |
| orders | 订单事实 ~300 笔（含 NULL） |
| monthly_targets | 月度目标 ~192 行 |
| refunds | 退款稀疏 ~25 笔 |

## 快速启动

### 1. 环境

- Python 3.11+（**必须使用 conda 环境 `wenshu`**）
- Node.js 18+

```bash
conda create -n wenshu python=3.11 -y
conda activate wenshu
```

### 2. 配置 API Key

编辑 `backend/.env`：

```
DEEPSEEK_API_KEY=sk-your-key-here
```

### 3. 后端

```bash
cd backend
conda activate wenshu
pip install -r requirements.txt
python scripts/preprocess.py      # 构建向量索引（首次）
python -m app.main                # http://localhost:8000
```

### 4. 前端

```bash
cd frontend
npm install
npm run dev                       # http://localhost:3000
```

### 5. Docker（可选）

```bash
docker compose up --build
```

## 主要 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| POST | `/api/chat` | Pipeline 非流式 |
| POST | `/api/chat/stream` | Pipeline SSE 流式 |
| POST | `/api/chat/agent` | ReAct Agent 非流式 |
| POST | `/api/chat/agent/stream` | Agent SSE（tool 事件 + done） |
| GET/DELETE | `/api/history` · `/api/history/{id}` | 对话历史 |
| POST | `/api/upload` | 上传 CSV/Excel |
| GET | `/api/export` | 导出查询结果 csv/xlsx |
| * | `/api/knowledge/*` | 知识库 CRUD |
| GET | `/api/dashboard/overview` | 数据看板（支持 `datasource_id`） |
| * | `/api/datasources/*` | 多数据源 CRUD / 测试 / SQL 审计 |
| GET/PUT | `/api/models` · `/api/models/config` | 模型供应商与密钥配置 |
| POST | `/api/feedback` | 用户反馈 |
| POST | `/api/rebuild-index` | 重建向量索引 |

## 前端能力

- 侧栏菜单：智能问数 · 数据看板 · 数据源 · 知识库 · 系统设置
- **Pipeline / Agent** 模式切换、数据源切换、模型配置（无需改 `.env`）
- 流式回答、思考提示、推荐追问、图表（柱/折/饼）
- 流程追踪（SQL / 工具调用）、导出、反馈、历史对话

## 测试

```bash
cd backend
conda activate wenshu
# 若本机使用 SOCKS 代理，需: pip install "httpx[socks]"
pytest tests/ -q
```

## 项目结构

```
wenshu/
├── backend/                    # FastAPI
│   ├── app/
│   │   ├── main.py             # 入口 / lifespan
│   │   ├── config.py           # 环境变量（路径锚定 backend/）
│   │   ├── logger.py           # loguru
│   │   ├── agent/              # ReAct Agent
│   │   ├── nl2sql/             # 翻译 / 纠错 / 意图 / 多轮 / Pipeline
│   │   ├── rag/                # 加载 / 切分 / 向量 / 检索 / 生成
│   │   ├── datasources/        # 多数据源（SQLite / MySQL / PG）
│   │   ├── models/             # LLM Provider + API Schema
│   │   ├── routes/             # HTTP API
│   │   ├── services/           # 会话 / 缓存 / 看板 / LLM 配置 / 知识库
│   │   ├── evaluation/         # 评测
│   │   └── middleware/         # 限流等
│   ├── data/                   # 见 backend/data/README.md
│   │   └── datasets/           # 演示 CSV + nl2sql_knowledge.json（入库）
│   ├── scripts/                # preprocess / rebuild_index / verify_startup
│   ├── tests/
│   └── requirements.txt
├── frontend/                   # Vue 3 + Pinia + Vite
│   └── src/
│       ├── views/              # 问数 / 看板 / 数据源 / 知识库 / 设置
│       ├── components/
│       ├── layouts/AppLayout.vue
│       ├── stores/chat.js
│       └── api/index.js
├── DEVELOPMENT_PLAN.md         # 功能路线
├── CLAUDE.md                   # 本仓库开发约定
└── docker-compose.yml
```

**目录约定（轻量）**

| 类型 | 位置 | 是否提交 |
|------|------|----------|
| 业务代码 | `backend/app/`、`frontend/src/` | 是 |
| 演示数据集 | `backend/data/datasets/` | 是 |
| 运行时库/会话/密钥配置 | `chroma_db/`、`*.db`、`llm_settings.json` 等 | 否（gitignore） |
| 日志与调试输出 | `logs/`、`*_out.txt` | 否 |

## 开发计划

见 [DEVELOPMENT_PLAN.md](./DEVELOPMENT_PLAN.md)。

## License

MIT
