# AI 开发任务书 — 工作流 C：智能对话与前端体验提升

> **目标**：多轮对话、意图识别、数据看板、用户反馈、前端动效  
> **工期**：约 4 周  
> **涉及文件**：后端 5 个新文件 + 修改 translator.py/pipeline.py；前端 2 个新组件 + 1 个新视图  
> **不与工作流 A/B 冲突**（除 main.py 追加路由的简单合并）  
> **启动指令**：将本文档直接喂给 AI，说"按此文档执行开发"

---

## 项目环境

- **项目根目录**: `c:\Users\zhy\Desktop\wenshu`
- **后端**: Python 3.10+ / FastAPI / SQLite / DeepSeek API / LangChain
- **前端**: Vue 3 (Composition API) / Pinia / Chart.js (通过 vue-chartjs) / 原生 CSS
- **后端启动**: `cd backend && python -m app.main`
- **前端启动**: `cd frontend && npm run dev`

---

## 关键参考代码

### 翻译器 (`backend/app/nl2sql/translator.py`)

核心类：
- `NL2SQLTranslator` — 将自然语言翻译为 SQL，接收 `(question, schema, rag_context)` → `sql`
- `AnswerGenerator` — 基于 SQL 结果生成回答，提供 `generate()` 和 `generate_stream()` 两种模式
- `RecommendedQuestionsGenerator` — 生成后续问题推荐

翻译流程：
```python
def translate(self, question, schema, rag_context) -> str:
    # 构建 system prompt (NL2SQL_SYSTEM_PROMPT)
    # 注入 FEW_SHOT_EXAMPLES
    # 调用 self.llm.invoke() 返回 SQL
```

### Pipeline (`backend/app/nl2sql/pipeline.py`)

核心类 `NL2SQLPipeline`：
- `query(question, conversation_id)` — 同步查询
- `query_stream(question)` — 流式查询
- `_get_rag_context(question)` — RAG 辅助检索
- `_fallback_rag(...)` — NL2SQL 失败时回退

### 前端 Store (`frontend/src/stores/chat.js`)

```javascript
// 关键状态
const currentConversationId = ref(null)
const messages = ref([])
const isStreaming = ref(false)
const recommendedQuestions = ref([])

// 关键方法
sendStream(question)  // 流式发送
stopStream()          // 中断
loadHistory()         // 加载历史
loadConversation(id)  // 加载指定对话
```

### 前端路由 (`frontend/src/main.js`)

```javascript
import { createRouter, createWebHistory } from 'vue-router'
const routes = [{ path: '/', component: Home }]
```

### 前端 API (`frontend/src/api/index.js`)

```javascript
import axios from 'axios'
const api = axios.create({ baseURL: '/api', timeout: 60000 })
export const sendMessage = (q, cid) => api.post('/chat', { question: q, conversation_id: cid })
export const sendMessageStream = (q, cid) => { /* fetch + AbortController */ }
export const getHistory = () => api.get('/history')
// 在此追加新 API 函数
```

### 前端 CSS 体系

- 全局变量定义在 `frontend/src/style.css`
- 核心变量: `--primary: #4f46e5`, `--primary-hover: #4338ca`, `--primary-light: #eef2ff`, `--bg: #f8fafc`, `--bg-card: #ffffff`, `--bg-sidebar: #1e293b`, `--border: #e2e8f0`, `--text: #1e293b`, `--text-secondary: #64748b`, `--success: #10b981`, `--danger: #ef4444`, `--warning: #f59e0b`, `--radius-sm: 8px`, `--radius: 12px`, `--shadow: 0 1px 3px rgba(0,0,0,0.08)`, `--shadow-lg: 0 10px 25px rgba(0,0,0,0.1)`, `--transition: 0.2s ease`

---

## 任务清单

### 任务 C1：多轮对话上下文

**目标**：让系统记住对话历史，支持"刚才那个省呢？""和去年比呢？"等追问。

**新建 `backend/app/nl2sql/multi_turn.py`**：

```python
"""多轮对话上下文管理器"""
from typing import List, Dict, Optional

MAX_CONTEXT_TURNS = 6  # 最多保留最近 6 轮对话

class ConversationContext:
    """管理单次对话的上下文"""
    
    def __init__(self, conversation_id: str):
        self.conversation_id = conversation_id
        self.turns: List[Dict] = []  # [{question, sql, answer_summary}]
    
    def add_turn(self, question: str, sql: str, answer: str) -> None:
        """添加一轮对话。answer 截断到 200 字符作为摘要"""
        self.turns.append({
            "question": question,
            "sql": sql,
            "answer_summary": answer[:200] if answer else "",
        })
        # 保留最近 N 轮
        if len(self.turns) > MAX_CONTEXT_TURNS:
            self.turns = self.turns[-MAX_CONTEXT_TURNS:]
    
    def get_context_prompt(self) -> str:
        """生成注入到 NL2SQL Prompt 的上下文文本"""
        if not self.turns:
            return ""
        lines = ["## 对话历史（按时间顺序，用于理解指代和追问）"]
        for i, turn in enumerate(self.turns, 1):
            lines.append(f"{i}. 用户问: {turn['question']}")
            lines.append(f"   SQL: {turn['sql'][:150]}")
            lines.append(f"   回答: {turn['answer_summary']}")
        return "\n".join(lines)


class MultiTurnManager:
    """管理所有对话的上下文"""
    
    def __init__(self):
        self._contexts: Dict[str, ConversationContext] = {}
    
    def get_context(self, conv_id: str) -> ConversationContext:
        if conv_id not in self._contexts:
            self._contexts[conv_id] = ConversationContext(conv_id)
        return self._contexts[conv_id]
    
    def remove_context(self, conv_id: str) -> None:
        self._contexts.pop(conv_id, None)
    
    def clear_all(self) -> int:
        count = len(self._contexts)
        self._contexts.clear()
        return count

# 全局单例
_manager = None
def get_multi_turn_manager() -> MultiTurnManager:
    global _manager
    if _manager is None: _manager = MultiTurnManager()
    return _manager
```

**修改 `backend/app/nl2sql/translator.py`**：

1. 在 `NL2SQL_TRANSLATOR_SYSTEM_PROMPT` 中已经包含参考示例，现在需要在 prompt 中追加一个变量 `{history}` 用于注入对话历史。找到 SystemMessage 构建处，添加：
```python
system_prompt = NL2SQL_SYSTEM_PROMPT.format(
    schema=schema,
    examples=examples,
    history=history_context if history_context else "无对话历史",
)
```

2. 修改 `NL2SQLTranslator.translate()` 方法签名，增加可选参数 `history_context: str = ""`：
```python
def translate(self, question: str, schema: str = "", rag_context: str = "", history_context: str = "") -> str:
```

3. 在 NL2SQL_SYSTEM_PROMPT 末尾追加：
```
## 对话历史
{history}

如果对话历史中包含指代（如"那个省""上个月""它"），请结合历史推断具体指向。
如果用户说"刚才那个""和去年比呢""再按品类分一下"，请结合上一轮的 SQL 和回答来生成新的 SQL。
```

**修改 `backend/app/nl2sql/pipeline.py`**：

在 `query()` 和 `query_stream()` 方法中：
```python
# 在调用 translator.translate() 之前
from app.nl2sql.multi_turn import get_multi_turn_manager
mtm = get_multi_turn_manager()

conv_ctx = None
if conversation_id:
    conv_ctx = mtm.get_context(conversation_id)

history_prompt = ""
if conv_ctx and conv_ctx.turns:
    history_prompt = conv_ctx.get_context_prompt()

# 传入翻译器
sql = self.translator.translate(question, schema, rag_context, history_prompt)
```

在成功生成回答后：
```python
if conv_ctx:
    conv_ctx.add_turn(question, sql, answer)
```

**验证**：
```
问题1: "2024年销售额最高的省份是哪个？"  → 得到结果
问题2: "它的退款率呢？"  → 应能推断"它"= 上一轮的省份，生成带 LEFT JOIN refunds 的查询
```

---

### 任务 C2：意图识别分流器

**目标**：前置识别用户意图，不同意图走不同处理流程。

**新建 `backend/app/nl2sql/intent.py`**：

```python
"""意图识别器 — 将用户问题分流到不同处理管线"""
from enum import Enum

class Intent(str, Enum):
    DATA_QUERY = "DATA_QUERY"            # 数据查询 → NL2SQL
    DATA_ANALYSIS = "DATA_ANALYSIS"      # 数据分析/洞察 → NL2SQL + 增强回答
    KNOWLEDGE_QA = "KNOWLEDGE_QA"        # 知识问答 → RAG
    CHITCHAT = "CHITCHAT"                # 闲聊 → 直接回复
    META = "META"                        # 系统元问题 → 直接回复

class IntentClassifier:
    """基于规则的意图分类器（快速、零延迟），复杂场景可升级为 LLM 分类"""
    
    # 闲聊关键词
    CHITCHAT_KEYWORDS = ["你好", "谢谢", "再见", "你是谁", "你能做什么", "介绍一下", "hello", "hi"]
    # 元问题关键词
    META_KEYWORDS = ["有哪些表", "表结构", "数据来源", "怎么用", "有哪些数据"]
    # 知识问答关键词
    KNOWLEDGE_KEYWORDS = ["什么是", "定义", "概念", "原理", "为什么", "怎么计算", "解释"]
    # 数据分析关键词（触发增强回答：洞察+建议）
    ANALYSIS_KEYWORDS = ["趋势", "预测", "建议", "优化", "原因分析", "为什么下降", "为什么增长", "异常"]
    
    @classmethod
    def classify(cls, question: str) -> Intent:
        q_lower = question.lower().strip()
        # 1. 闲聊检查
        for kw in cls.CHITCHAT_KEYWORDS:
            if kw in q_lower:
                return Intent.CHITCHAT
        # 2. 元问题检查
        for kw in cls.META_KEYWORDS:
            if kw in q_lower:
                return Intent.META
        # 3. 知识问答检查
        for kw in cls.KNOWLEDGE_KEYWORDS:
            if kw in q_lower:
                return Intent.KNOWLEDGE_QA
        # 4. 数据分析检查
        for kw in cls.ANALYSIS_KEYWORDS:
            if kw in q_lower:
                return Intent.DATA_ANALYSIS
        # 5. 默认数据查询
        return Intent.DATA_QUERY
```

**修改 `backend/app/nl2sql/pipeline.py`**：

在 `query()` 方法中添加意图路由：
```python
from app.nl2sql.intent import IntentClassifier, Intent

intent = IntentClassifier.classify(question)

if intent == Intent.CHITCHAT:
    return self._handle_chitchat(question, conv_id)
elif intent == Intent.META:
    return self._handle_meta(question, conv_id)
elif intent == Intent.KNOWLEDGE_QA:
    return self._fallback_rag(question, conv_id, rag_context, rag_docs, start_time)
# DATA_QUERY / DATA_ANALYSIS 走标准 NL2SQL 流程
```

实现 `_handle_chitchat()` 和 `_handle_meta()` 方法：
```python
def _handle_chitchat(self, question, conv_id):
    """处理闲聊"""
    greetings = {"你好": "你好！我是智能问数助手，可以帮你查询和分析电商数据。试试问我'销售额最高的品类是什么？'",
                 "谢谢": "不客气！随时可以继续提问。",
                 ...}
    return {...}

def _handle_meta(self, question, conv_id):
    """处理系统元问题"""
    schema = get_schema_info()
    answer = f"当前数据库包含以下表：\n\n{schema}\n\n你可以直接问我数据分析相关的问题。"
    return {...}
```

对于 `Intent.DATA_ANALYSIS`，在生成回答的 System Prompt 中添加额外指令：
```
用户正在询问数据分析类问题。请提供：
1. 数据查询结果
2. 对结果的简要解读（趋势、对比、亮点）
3. 如果数据支持，给出一个相关的后续分析建议
```

**验证**：
```
"你好" → 走 CHITCHAT，返回友好问候
"有哪些表" → 走 META，返回表结构
"销售额趋势怎么样" → 走 DATA_ANALYSIS，回答带解读和建议
"退款率最高的品类" → 走 DATA_QUERY，正常 NL2SQL
```

---

### 任务 C3：数据看板 Dashboard

**目标**：首页展示关键指标卡片，让用户一目了然。

**新建 `frontend/src/views/Dashboard.vue`**：

**布局设计**：
```
┌─────────────────────────────────────────────┐
│  📊 数据看板                  最后的更新时间  │
├──────────┬──────────┬──────────┬────────────┤
│ 总销售额  │ 总订单数  │ 客户数    │ 退款率     │
│ ¥ 1.2M   │ 300      │ 100      │ 8.3%      │
│ ↑ 环比    │ 图表      │ 🔵        │ 🔴        │
├──────────┴──────────┴──────────┴────────────┤
│  各品类销售额排名（柱状图） 50%               │
│  ┌─────────────────────────────────────────┐│
│  │  Chart.js Bar Chart                     ││
│  └─────────────────────────────────────────┘│
├──────────────────────┬──────────────────────┤
│  月度销售趋势（折线图）│  省份销售分布（饼图） │
│  ┌─────────────────┐ │ ┌──────────────────┐ │
│  │ Line Chart      │ │ │ Pie Chart        │ │
│  └─────────────────┘ │ └──────────────────┘ │
├──────────────────────┴──────────────────────┤
│  最近热门问题  │  高频查询表                │
└─────────────────────────────────────────────┘
```

**数据来源**：在 `onMounted` 中并行调用多个 API 获取统计数据。

**新建 `backend/app/services/analytics.py`**：

```python
"""数据分析服务 — 聚合统计、热门查询记录"""
from app.nl2sql.database import execute_sql

def get_overview_stats() -> dict:
    """获取概览统计"""
    # 总销售额、总订单数、客户数、退款率
    queries = {
        "total_revenue": "SELECT SUM([订单金额_元]) FROM [orders] WHERE [订单状态]='已完成'",
        "total_orders": "SELECT COUNT(*) FROM [orders]",
        "total_customers": "SELECT COUNT(*) FROM [customers]",
        "refund_rate": "SELECT CAST(COUNT(DISTINCT [r].[订单ID]) AS REAL)*100.0/COUNT(DISTINCT [o].[订单ID]) FROM [orders] [o] LEFT JOIN [refunds] [r] ON [o].[订单ID]=[r].[订单ID]",
        "category_revenue": "SELECT [p].[品类], SUM([o].[订单金额_元]) FROM [orders] [o] JOIN [products] [p] ON [o].[商品ID]=[p].[商品ID] WHERE [o].[订单状态]='已完成' GROUP BY [p].[品类] ORDER BY SUM([o].[订单金额_元]) DESC",
        "monthly_trend": "SELECT STRFTIME('%Y-%m', [日期]) AS 月, SUM([订单金额_元]) FROM [orders] WHERE [订单状态]='已完成' GROUP BY 月 ORDER BY 月",
        "province_distribution": "SELECT [收货省份], SUM([订单金额_元]) FROM [orders] WHERE [订单状态]='已完成' GROUP BY [收货省份] ORDER BY SUM([订单金额_元]) DESC",
    }
    return execute_all(queries)
```

**新建 `backend/app/routes/analytics.py`**：

```python
from fastapi import APIRouter
from app.services.analytics import get_overview_stats

analytics_router = APIRouter(prefix="/api", tags=["analytics"])

@analytics_router.get("/dashboard/overview")
async def dashboard_overview():
    """看板概览数据"""
    return get_overview_stats()
```

**修改 `frontend/src/main.js`**，添加路由：
```javascript
import Dashboard from './views/Dashboard.vue'
const routes = [
  { path: '/', component: Home },
  { path: '/dashboard', component: Dashboard },
]
```

**修改 `frontend/src/views/Home.vue`**，在 topbar 标题旁添加导航链接：
```html
<router-link to="/dashboard" class="dashboard-link">
  <svg>...</svg> 数据看板
</router-link>
```

---

### 任务 C4：用户反馈系统 + 前端动效

**目标**：用户可对回答点赞/踩，收集反馈用于优化 Few-shot；前端增加交互动效。

#### 反馈后端

**新建 `backend/app/routes/feedback.py`**：
```python
feedback_router = APIRouter(prefix="/api", tags=["feedback"])

@feedback_router.post("/feedback")
async def submit_feedback(
    message_id: str,
    rating: str,  # "like" 或 "dislike"
    comment: str = None,  # 可选评语
):
    """记录用户反馈到 JSON 文件"""
    # 保存到 data/feedback.json
    feedback = {
        "message_id": message_id,
        "rating": rating,
        "comment": comment,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    # 追加写入
    ...

@feedback_router.get("/feedback/stats")
async def feedback_stats():
    """反馈统计"""
    # 总反馈数、好评率、最近反馈列表
    ...
```

#### 反馈前端

**新建 `frontend/src/components/FeedbackBar.vue`**：

显示在每条 AI 回复底部：
```html
<div class="feedback-bar">
  <button class="feedback-btn" :class="{ active: rating === 'like' }" @click="rate('like')">
    <svg>👍</svg> 有帮助
  </button>
  <button class="feedback-btn" :class="{ active: rating === 'dislike' }" @click="rate('dislike')">
    <svg>👎</svg> 不准确
  </button>
  <span v-if="submitted" class="feedback-thanks">感谢反馈！</span>
</div>
```

**修改 `frontend/src/components/ChatMessage.vue`**，在消息底部引入 `FeedbackBar`：
```javascript
import FeedbackBar from './FeedbackBar.vue'
// 在模板中 AI 回复区域底部添加 <FeedbackBar v-if="message.role === 'assistant' && !message.isStreaming" />
```

#### 前端动效

1. **消息滑入动画**：在 `ChatMessage.vue` 的样式中添加：
```css
.chat-message {
  animation: slideInUp 0.3s ease-out;
}
@keyframes slideInUp {
  from { opacity: 0; transform: translateY(16px); }
  to { opacity: 1; transform: translateY(0); }
}
```

2. **流式输出光标闪烁**：在正在流式输出的消息内容后添加闪烁光标：
```css
.streaming-cursor::after {
  content: '▍';
  animation: blink 1s step-end infinite;
  color: var(--primary);
}
@keyframes blink {
  50% { opacity: 0; }
}
```

3. **侧边栏滑入**：侧边栏已有 `transform: translateX(-100%)` → `translateX(0)` 过渡。

4. **按钮波纹效果**：对所有操作按钮添加点击波纹：
```css
.btn-ripple {
  position: relative;
  overflow: hidden;
}
.btn-ripple::after {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(circle, rgba(255,255,255,0.3) 10%, transparent 10%);
  opacity: 0;
  transition: opacity 0.3s;
}
.btn-ripple:active::after {
  opacity: 1;
  transition: 0s;
}
```

5. **图表进入动画**：在 `DataChart.vue` 中添加：
```css
.data-chart {
  animation: fadeIn 0.5s ease-out 0.2s both;
}
@keyframes fadeIn {
  from { opacity: 0; transform: scale(0.95); }
  to { opacity: 1; transform: scale(1); }
}
```

---

### 任务 C5：图表增强

**目标**：图表支持导出为 PNG，增加图表标题和自定义配色。

**修改 `frontend/src/components/DataChart.vue`**：

1. 添加图表标题显示（从 chart_data 中提取或自动生成）
2. 添加导出 PNG 按钮（使用 canvas.toDataURL()）：
```javascript
function exportPNG() {
  const canvas = chartRef.value?.canvas
  if (canvas) {
    const link = document.createElement('a')
    link.download = 'chart.png'
    link.href = canvas.toDataURL('image/png')
    link.click()
  }
}
```
3. 统一定制 Chart.js 配色方案（使用 `--primary: #4f46e5` 等 CSS 变量的色值）：
```javascript
const CHART_COLORS = [
  '#4f46e5', '#06b6d4', '#10b981', '#f59e0b', '#ef4444',
  '#8b5cf6', '#ec4899', '#14b8a6', '#f97316', '#6366f1',
]
```

**修改 `backend/app/nl2sql/translator.py`**：

在 `AnswerGenerator.ANSWER_SYSTEM_PROMPT` 中增强图表生成指令：
```
7. 图表数据生成规则：
   - 饼图(pie)：占比类问题（如各品类销售占比、支付方式分布）
   - 柱状图(bar)：排名对比（如TOP5省份、各品类对比）
   - 折线图(line)：时间趋势（如月度销售额、累计增长）
   - 图表标题(可选)：添加 title 字段
   - 颜色(可选)：添加 colorScheme 字段，从 ['indigo','ocean','forest','sunset','rose','violet'] 中选择
```

---

## 执行顺序建议

```
第 1 周：C1(多轮对话上下文) → 验证追问生效
第 2 周：C2(意图识别) → 验证分流正确 + C3(数据看板后端)
第 3 周：C3(数据看板前端) → C5(图表增强) → 验证看板展示
第 4 周：C4(反馈系统+动效) → 整体联调
```

---

## 验收标准

1. 追问"它的退款率呢？"能正确关联上一轮的查询结果
2. 输入"你好"返回问候语而非 SQL 错误
3. `/dashboard` 页面正常展示概览卡片 + 至少 3 个图表
4. 点赞/踩按钮可用，反馈数据写入文件
5. 消息、图表、侧边栏有流畅的进入动效
6. 图表可导出为 PNG

## 启动提示词

```
请严格按照本文档执行开发任务，按 C1→C2→C3→C4→C5 顺序完成。
每完成一个任务，运行对应的验证确认后再继续。
注意：
- 所有新建路由在 main.py 注册时追加到已有路由之后
- 所有新建视图在 main.js 注册时追加到已有路由之后
- 前端所有新建组件/视图样式与现有深色主题一致
- 不要修改工作流 A/B 负责的文件（database.py, exceptions.py, cache.py, rate_limit.py, 
  file_upload.py, conversation_store.py, knowledge_manager.py, export_service.py 等）
```
