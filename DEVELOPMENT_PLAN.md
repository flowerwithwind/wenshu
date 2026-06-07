# 智能问数系统 (SmartQA) — 开发计划

> 版本: v1.0  
> 更新日期: 2026-06-07  
> 当前状态: MVP 已完成，数据集已升级为电商场景

---

## 一、项目现状

### 1.1 已完成功能

| 模块 | 完成度 | 说明 |
|------|--------|------|
| NL2SQL 翻译 | 85% | 规则 + LLM 混合，**5 张表（星型模型）**、28 个 Few-shot 示例（覆盖 JOIN/CTE/窗口/NULL） |
| RAG 辅助检索 | 85% | 同义词映射、领域映射、Schema 增强，NL2SQL 失败回退，**162 个向量块** |
| SQL 执行 | 90% | SQLite 执行，CSV 自动建表（含 NULL 处理），JOIN 索引加速 |
| 流式回答 | 90% | SSE 流式输出，支持前端中断 |
| 图表可视化 | 85% | Chart.js 柱状图/折线图/饼图，LLM 自动生成 chart_data |
| 对话历史 | 60% | CRUD 完整，但**内存存储**，重启丢失 |
| 前端 UI | 90% | 流程追踪、来源引用、推荐问题、响应式布局 |
| 数据上传 | 0% | 仅支持手动放置 CSV 到 `datasets/` 目录 |
| **数据集** | **100%** | **电商场景：customers(100人) + products(40款) + orders(300笔,含NULL) + monthly_targets(192行) + refunds(25笔,稀疏)** |

### 1.2 当前架构

```
用户提问 → NL2SQL Pipeline（主）→ SQLite 5表星型查询 → 自然语言回答 + 图表
              ↓ 失败时回退
         RAG Pipeline（辅助）→ 向量检索 → 知识库回答
```

### 1.3 数据模型

```
      customers (100人)           products (40款)
          │ 客户ID                    │ 商品ID
          ▼                           ▼
      orders (300笔) ◄────────── monthly_targets (192行)
          │ 订单ID                    年份+月份+品类
          ▼
      refunds (25笔, 稀疏)
```

**NL2SQL 可测试的复杂查询类型：**
- INNER JOIN / LEFT JOIN / 3表关联
- 子查询 / CTE (WITH) / 窗口函数 (LAG, RANK)
- NULL 值处理 (COALESCE, IS NULL)
- GROUP BY + HAVING / CASE WHEN
- 日期范围 / 同比环比 / 达成率计算

### 1.4 当前短板

1. **对话无持久化** — 内存 `conversation_store` dict，服务重启即丢失
2. **数据不可上传** — 用户无法自行导入数据，只能使用预置 CSV
3. **无多轮对话** — 每次提问独立，不记忆历史上下文
4. **无 SQL 安全校验** — DELETE/UPDATE/DROP 等危险操作未拦截
5. **无用户体系** — 无认证、无多租户
6. **数据源单一** — 仅 CSV → SQLite，不支持外部数据库

---

## 二、总体路线图

```
第一阶段（夯实基础）  →  第二阶段（提升体验）  →  第三阶段（能力扩展）  →  第四阶段（智能化）
    1-2 周                  2-4 周                  1-2 月                   长期
```

---

## 三、第一阶段：夯实基础（1-2 周）

> 目标：补全核心缺失能力，让系统具备生产可用性

### 3.1 对话持久化

**现状**：`backend/app/routes/chat.py` 中 `conversation_store: dict = {}` 纯内存存储。

**方案**：
- 使用 SQLite 存储对话历史（与现有数据 SQLite 分离，用独立 `conversations.db`）
- 新建 `backend/app/models/conversation.py` 定义数据模型
- 新建 `backend/app/services/conversation_store.py` 封装 CRUD 操作

**数据表设计**：
```sql
-- 对话表
CREATE TABLE conversations (
    id TEXT PRIMARY KEY,
    title TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 消息表
CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
    question TEXT,
    answer TEXT,
    sql TEXT,
    sql_result TEXT,          -- JSON 序列化
    sources TEXT,             -- JSON 序列化
    chart_data TEXT,          -- JSON 序列化
    response_time_ms REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);
```

**涉及文件**：
- 新建 `backend/app/services/conversation_store.py`
- 修改 `backend/app/routes/chat.py`（替换 dict 操作为 DB 操作）
- 修改 `backend/app/models/schemas.py`（新增相关 Schema）

### 3.2 SQL 安全校验

**现状**：`NL2SQLTranslator._is_valid_sql()` 仅检查是否以 SELECT 开头，危险操作未拦截。

**方案**：
- 在 `backend/app/nl2sql/database.py` 的 `execute_sql()` 中添加安全校验层
- 使用 `sqlparse` 库解析 SQL，识别 DML/DDL 语句
- 拦截规则：
  - 只允许 SELECT 语句
  - 禁止 DROP、DELETE、UPDATE、INSERT、ALTER、CREATE、TRUNCATE
  - 限制结果行数（默认 1000 行）
  - 设置查询超时（默认 30 秒）

**涉及文件**：
- 修改 `backend/app/nl2sql/database.py`
- 可选：`pip install sqlparse`

**代码示例**：
```python
import sqlparse

ALLOWED_STATEMENTS = {"SELECT"}
FORBIDDEN_KEYWORDS = {"DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE", "TRUNCATE", "EXEC", "EXECUTE"}

def validate_sql(sql: str):
    sql_upper = sql.upper()
    for kw in FORBIDDEN_KEYWORDS:
        if kw in sql_upper:
            raise ValueError(f"不允许执行包含 {kw} 的 SQL 语句")
    
    parsed = sqlparse.parse(sql)
    for stmt in parsed:
        if stmt.get_type() not in ALLOWED_STATEMENTS:
            raise ValueError(f"仅允许 SELECT 查询，不支持: {stmt.get_type()}")
```

### 3.3 错误处理细化

**现状**：`/api/chat` 路由中统一 `HTTPException(status_code=500)`，前端只显示笼统错误。

**方案**：
- 定义错误码枚举，区分不同错误场景
- 后端返回结构化错误：`{ "error_code": "SQL_GENERATION_FAILED", "message": "无法将问题转换为 SQL", "detail": "..." }`
- 前端根据 error_code 显示针对性的友好提示

**错误分类**：
| 错误码 | 场景 | 用户提示 |
|--------|------|---------|
| `SQL_GENERATION_FAILED` | LLM 返回无效 SQL | "抱歉，无法将您的问题转换为数据查询，请换一种问法" |
| `SQL_EXECUTION_ERROR` | SQL 语法错误 | "数据查询语句有误，请尝试更具体地描述您的问题" |
| `SQL_EMPTY_RESULT` | 查询结果为空 | "未找到匹配的数据，请检查查询条件" |
| `SQL_TIMEOUT` | 查询超时 | "查询超时，请缩小查询范围后重试" |
| `SAFETY_VIOLATION` | 危险 SQL | "检测到不安全的查询操作" |
| `LLM_SERVICE_ERROR` | 模型调用失败 | "AI 服务暂时不可用，请稍后重试" |
| `DATABASE_ERROR` | 数据库异常 | "数据服务异常，请稍后重试" |

**涉及文件**：
- 新建 `backend/app/exceptions.py`
- 修改 `backend/app/routes/chat.py`
- 修改 `frontend/src/stores/chat.js`

### 3.4 数据上传功能

**现状**：用户只能手动放 CSV 文件到 `backend/data/datasets/`。

**方案**：
- 后端新增 `POST /api/upload` 接口，接收 CSV/Excel 文件
- 上传后自动执行：解析文件 → 建表 → 插入数据 → 重建向量索引
- 前端新增上传入口（拖拽上传区域 + 文件选择器）
- 支持字段：文件上传、表名自定义、字段描述补充

**涉及文件**：
- 修改 `backend/app/routes/chat.py`（新增 `/api/upload` 路由）
- 新建 `backend/app/services/file_upload.py`
- 新建或修改 `frontend/src/components/FileUpload.vue`
- 修改 `frontend/src/views/Home.vue`（集成本上传入口）

---

## 四、第二阶段：提升体验（2-4 周）

> 目标：让系统更智能、更流畅、更好用

### 4.1 多轮对话上下文

**方案**：
- 在 `NL2SQLPipeline.query()` 中注入历史对话
- 将最近 N 轮（如 5 轮）Q&A 传入 LLM 的系统提示词
- 支持追问："那广东呢？"（自动关联上一轮查询的省份）
- 支持对比："和去年对比呢？"（自动关联上一轮查询的年份）

**技术要点**：
- Prompt 设计：在 System Prompt 中追加 `## 历史对话\n{history}`
- 上下文窗口管理：长对话时自动摘要或截断旧消息
- 前端：侧边栏对话列表加入"继续对话"按钮

**涉及文件**：
- 修改 `backend/app/nl2sql/translator.py`（Prompt 注入历史）
- 修改 `backend/app/nl2sql/pipeline.py`（传入历史对话）
- 修改 `backend/app/routes/chat.py`（从 DB 读取历史）

### 4.2 查询缓存

**方案**：
- 对问题文本做 hash，SQLite 缓存结果
- 缓存策略：相同问题 1 小时内命中缓存
- 缓存表结构：`question_hash | question | sql | result_json | chart_data | created_at | hit_count`

**涉及文件**：
- 新建 `backend/app/services/query_cache.py`
- 修改 `backend/app/nl2sql/pipeline.py`

### 4.3 数据导出

**方案**：
- 后端新增 `POST /api/export` 接口，接收查询结果和格式参数
- 支持导出格式：CSV、Excel、PNG（图表截图）
- 前端：在消息卡片下方增加"导出"按钮

**涉及文件**：
- 新建 `backend/app/services/exporter.py`
- 修改 `backend/app/routes/chat.py`
- 修改 `frontend/src/components/ChatMessage.vue`

### 4.4 意图识别

**方案**：
- 在 NL2SQL 翻译前增加一层意图分类
- 分类器 Prompt：
  - `data_query`：需要查询数据库的问题 → 走 NL2SQL
  - `knowledge_qa`：知识问答 → 走 RAG
  - `chat`：闲聊 → 直接 LLM 回答
  - `data_analysis`：需要分析/计算 → NL2SQL + 分析
- 用轻量 LLM 调用（temperature=0，max_tokens=50）做意图分类

**涉及文件**：
- 新建 `backend/app/nl2sql/intent_classifier.py`
- 修改 `backend/app/nl2sql/pipeline.py`

### 4.5 Agent 化（基础版）

**方案**：
- 引入 ReAct 模式或简单的多步推理
- 流程：
  1. 用户提问 → 意图识别
  2. LLM 判断是否需要先查表结构 → 如需则先 `SELECT * FROM [table] LIMIT 1`
  3. 生成 SQL → 执行
  4. 检查结果 → 若为空或异常，自动修正 SQL 重试（最多 2 次）
  5. 生成回答 + 图表

**涉及文件**：
- 新建 `backend/app/nl2sql/agent.py`
- 修改 `backend/app/nl2sql/pipeline.py`

### 4.6 用户反馈机制

**方案**：
- 每条 AI 回答下方增加 👍 / 👎 按钮
- 反馈数据存储到数据库
- 被踩的回答自动记录到"待优化"列表
- 后端新增 `POST /api/feedback` 接口

**涉及文件**：
- 修改 `backend/app/routes/chat.py`
- 修改 `frontend/src/components/ChatMessage.vue`
- 修改 `frontend/src/stores/chat.js`

---

## 五、第三阶段：能力扩展（1-2 月）

> 目标：从单机工具扩展为多数据源平台

### 5.1 多数据源接入

**方案**：
- 支持连接外部数据库：MySQL、PostgreSQL、ClickHouse
- 用户在前端配置连接信息（host、port、user、password、database）
- 后端动态创建连接池，读取表结构
- 数据源信息加密存储

**技术要点**：
- 使用 sqlalchemy 统一数据库接口
- 连接信息用 AES 加密存储
- 前端：数据源管理页面（增删改查、测试连接）

**涉及文件**：
- 新建 `backend/app/services/datasource_manager.py`
- 新建 `backend/app/routes/datasource.py`
- 新建 `frontend/src/views/DataSource.vue`
- 新建 `frontend/src/components/DataSourceForm.vue`

### 5.2 知识库在线管理

**方案**：
- 前端提供界面管理 NL2SQL 知识库（`nl2sql_knowledge.json`）
- 功能：查看/添加/编辑/删除 Few-shot 示例、同义词、领域映射
- 操作后自动重建向量索引

**涉及文件**：
- 新建 `backend/app/routes/knowledge.py`
- 新建 `frontend/src/views/Knowledge.vue`
- 新建 `frontend/src/components/KnowledgeEditor.vue`

### 5.3 数据看板 Dashboard

**方案**：
- 首页增加 Dashboard 视图
- 展示指标卡片：总数据表数、总记录数、今日查询次数、平均响应时间
- 热门问题 Top 10、热门表 Top 5
- 查询趋势图（7 天/30 天）

**涉及文件**：
- 新建 `backend/app/routes/dashboard.py`
- 新建 `frontend/src/views/Dashboard.vue`

### 5.4 NL2SQL 准确率专项优化

**方案**：
- ACL (Add Column Linking)：在 Prompt 中更精确地描述列语义
- 动态 Few-shot：根据问题相似度从知识库中检索最相关的 3-5 个示例
- 结果验证：SQL 执行后检查结果是否符合预期，不符合则修正
- 收集用户修正后的 SQL，用于后续优化

### 5.5 定时报表

**方案**：
- 用户可配置定时任务：每天/每周/每月执行指定 SQL 查询
- 生成报表并通过邮件/企业微信/钉钉推送
- 使用 APScheduler 实现定时调度

**涉及文件**：
- 新建 `backend/app/services/scheduler.py`
- 新建 `backend/app/routes/schedule.py`
- 新建 `frontend/src/views/Schedule.vue`

---

## 六、第四阶段：智能化（长期）

> 目标：从"工具"进化为"智能分析助手"

### 6.1 NL2SQL 微调模型

- 收集用户真实 Query-SQL 对（脱敏后）
- 基于 Qwen2.5-Coder 或 DeepSeek-Coder 微调专有模型
- 目标：降低延迟、减少成本、提升准确率

### 6.2 自动数据洞察

- 回答完问题后，自动对结果数据做统计检验
- 发现异常值、趋势拐点、相关性时主动提示
- 示例："广东 GDP 增速比全国平均高 1.2 个百分点，近三年呈加速趋势"

### 6.3 语音输入

- 集成 Web Speech API 或第三方 STT 服务
- 前端增加语音输入按钮
- 支持中英文语音识别

### 6.4 预测分析

- 基于历史数据做简单趋势预测（线性回归 / 移动平均）
- 在回答中附带预测值
- 示例："按照当前趋势，2025 年 GDP 预计将达到 XX 万亿元"

### 6.5 数据故事

- 将多个相关查询串联为"数据故事"
- 自动生成章节标题和过渡文案
- 示例："中国宏观经济十年回顾"（GDP 增长 → 产业结构变迁 → 人口变化 → 区域发展）

### 6.6 API 对外开放

- 将问数能力封装为 RESTful API
- 提供 API Key 管理
- 限流、配额管理
- SDK 文档生成

---

## 七、技术债务清单

无论哪个阶段，以下事项应持续关注：

| 项目 | 说明 |
|------|------|
| 单元测试 | 当前无测试，核心模块（NL2SQL、RAG、Database）需要有测试覆盖 |
| 日志系统 | 统一日志格式，分级记录（DEBUG/INFO/WARN/ERROR），支持日志轮转 |
| 配置管理 | 将硬编码的 Prompt、参数提取到配置文件 |
| 性能监控 | 接入 Prometheus 或自定义埋点，监控 API 响应时间、LLM 调用次数 |
| 代码重构 | `backend/app/routes/chat.py` 职责过重，需要拆分 Service 层 |
| 前端状态管理 | Pinia store 中流式处理逻辑较复杂，可抽取 composable |
| 依赖升级 | 定期升级 LangChain、FastAPI 等核心依赖 |

---

## 八、附录

### 8.1 项目结构扩展后

```
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── exceptions.py            # [新增] 错误码定义
│   │   ├── rag/                     # RAG 模块
│   │   ├── nl2sql/                  # NL2SQL 模块
│   │   │   ├── agent.py             # [新增] Agent 多步推理
│   │   │   ├── intent_classifier.py # [新增] 意图识别
│   │   │   ├── database.py
│   │   │   ├── pipeline.py
│   │   │   └── translator.py
│   │   ├── routes/
│   │   │   ├── chat.py
│   │   │   ├── datasource.py        # [新增] 数据源管理
│   │   │   ├── knowledge.py         # [新增] 知识库管理
│   │   │   ├── dashboard.py         # [新增] 数据看板
│   │   │   ├── schedule.py          # [新增] 定时报表
│   │   │   └── export.py            # [新增] 数据导出
│   │   ├── services/
│   │   │   ├── conversation_store.py # [新增] 对话持久化
│   │   │   ├── query_cache.py        # [新增] 查询缓存
│   │   │   ├── file_upload.py        # [新增] 文件上传
│   │   │   ├── exporter.py           # [新增] 数据导出
│   │   │   ├── datasource_manager.py # [新增] 数据源管理
│   │   │   └── scheduler.py          # [新增] 定时调度
│   │   └── models/
│   │       └── schemas.py
│   ├── data/
│   │   ├── datasets/
│   │   ├── conversations.db          # [新增] 对话持久化
│   │   └── query_cache.db            # [新增] 查询缓存
│   └── tests/                        # [新增] 测试目录
│       ├── test_nl2sql.py
│       ├── test_rag.py
│       └── test_database.py
├── frontend/
│   ├── src/
│   │   ├── views/
│   │   │   ├── Home.vue
│   │   │   ├── Dashboard.vue         # [新增]
│   │   │   ├── Knowledge.vue         # [新增]
│   │   │   ├── DataSource.vue        # [新增]
│   │   │   └── Schedule.vue          # [新增]
│   │   ├── components/
│   │   │   ├── ChatMessage.vue
│   │   │   ├── ChatInput.vue
│   │   │   ├── DataChart.vue
│   │   │   ├── SourceCitation.vue
│   │   │   ├── WorkflowTrace.vue
│   │   │   ├── FileUpload.vue         # [新增]
│   │   │   ├── DataSourceForm.vue     # [新增]
│   │   │   └── KnowledgeEditor.vue    # [新增]
│   │   ├── stores/
│   │   │   ├── chat.js
│   │   │   ├── dashboard.js           # [新增]
│   │   │   └── datasource.js          # [新增]
│   │   └── api/
│   │       └── index.js
│   └── package.json
└── DEVELOPMENT_PLAN.md
```

### 8.2 核心依赖清单

| 阶段 | 新增依赖 |
|------|---------|
| 阶段一 | `sqlparse`（SQL 解析）、`openpyxl`（Excel 读取） |
| 阶段二 | 无新增（复用现有依赖） |
| 阶段三 | `sqlalchemy[asyncio]`、`aiomysql`/`asyncpg`、`APScheduler`、`cryptography` |
| 阶段四 | `scikit-learn`（预测）、`torch`（微调） |