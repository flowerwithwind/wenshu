# 智能问数系统 (SmartQA)

基于 LangChain + RAG 架构的智能数据问答系统，集成 DeepSeek-V4-Pro 大模型，支持自然语言查询结构化和非结构化数据。

## 技术栈

- **后端**: FastAPI + LangChain + ChromaDB + sentence-transformers
- **前端**: Vue 3 + Pinia + Chart.js + Markdown 渲染
- **模型**: DeepSeek-V4-Pro（OpenAI 兼容 API）
- **嵌入**: paraphrase-multilingual-MiniLM-L12-v2

## 知识库数据集

| 数据集 | 内容 |
|--------|------|
| 中国宏观经济 (2010-2024) | GDP、产业结构、消费、进出口、投资 |
| 中国人口 (2010-2024) | 人口总量、城镇化率、出生人口 |
| 企业营收 (2023) | 15 家知名企业营收、利润、员工规模 |
| 各省 GDP (2023) | 15 省份 GDP 总量、增速、人均 |

## 快速启动

### 1. 环境准备

- Python 3.11
- Node.js 18+

### 2. 配置 API Key

编辑 `backend/.env`，填入你的 DeepSeek API Key：

```
DEEPSEEK_API_KEY=sk-your-key-here
```

### 3. 后端

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/preprocess.py      # 生成数据集并构建向量索引
python -m app.main                # http://localhost:8000
```

### 4. 前端

```bash
cd frontend
npm install
npm run dev                       # http://localhost:3000
```

## 项目结构

```
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI 入口
│   │   ├── config.py             # 全局配置
│   │   ├── rag/                  # RAG 核心组件
│   │   │   ├── loader.py         # 文档加载器
│   │   │   ├── splitter.py       # 文本分割器
│   │   │   ├── vectorstore.py    # 向量存储管理
│   │   │   ├── retriever.py      # 智能检索器
│   │   │   ├── generator.py      # 大模型生成器
│   │   │   └── pipeline.py       # RAG 流程编排
│   │   ├── routes/chat.py        # API 路由
│   │   └── models/schemas.py     # 数据模型
│   ├── data/datasets/            # 公开数据集
│   ├── scripts/preprocess.py     # 数据预处理
│   ├── requirements.txt
│   └── .env
├── frontend/
│   ├── src/
│   │   ├── views/Home.vue        # 主界面
│   │   ├── components/           # ChatInput/Message/Chart/Source
│   │   ├── stores/chat.js        # 状态管理
│   │   └── api/index.js          # API 封装
│   └── package.json
└── README.md
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| POST | `/api/chat` | 问答（非流式） |
| POST | `/api/chat/stream` | 问答（SSE 流式） |
| GET | `/api/history` | 对话历史 |
| POST | `/api/rebuild-index` | 重建向量索引 |

## License

MIT