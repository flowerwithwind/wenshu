# AI 开发任务书 — 工作流 A：后端基础设施强化

> **目标**：提升系统安全性、可靠性、可观测性  
> **工期**：约 4 周（可按任务拆分并行执行）  
> **涉及文件**：仅后端，不与工作流 B/C 冲突  
> **启动指令**：将本文档直接喂给 AI，说"按此文档执行开发"

---

## 项目环境

- **项目根目录**: `c:\Users\zhy\Desktop\wenshu`
- **后端**: Python 3.10+ / FastAPI / SQLite / DeepSeek API
- **后端入口**: `backend/app/main.py`，启动命令 `python -m app.main`
- **包管理**: pip，`backend/requirements.txt`
- **测试框架**: pytest（需安装）

### 已有依赖（requirements.txt 已有）
```
fastapi, uvicorn, langchain-openai, pydantic, python-dotenv, 
chromadb, sentence-transformers, pandas, openpyxl, sqlparse
```

若 `sqlparse`、`pytest`、`pytest-asyncio`、`httpx` 未安装，请在任务中自行安装。

---

## 当前架构关键信息

### 数据库模块 (`backend/app/nl2sql/database.py`)
- `execute_sql(sql)` 直接执行任意 SQL，**无安全检查**
- `get_connection()` 创建 SQLite 连接，无超时
- 没有查询缓存

### 路由模块 (`backend/app/routes/chat.py`)
- 所有异常统一 `HTTPException(status_code=500, detail=str(e))`
- 无错误分类，无错误码

### Schema (`backend/app/models/schemas.py`)
- 已有 ChatRequest, ChatResponse, SourceDocument, SQLResult, DatasetInfo, HistoryItem, ConversationList, HealthResponse

### Config (`backend/app/config.py`)  
- 已有 DEEPSEEK_API_KEY, EMBEDDING_MODEL, CHROMA_PERSIST_DIR, CHUNK_SIZE, RETRIEVER_K, CORS_ORIGINS, DATASET_DIR 等

---

## 任务清单

### 任务 A1：SQL 安全校验层

**目标**：拦截 DROP/DELETE/UPDATE/INSERT/ALTER/CREATE/TRUNCATE 等危险操作，只允许 SELECT/EXPLAIN/WITH SELECT。

**修改文件**：`backend/app/nl2sql/database.py`

**实现要点**：
1. 在 `execute_sql()` 函数开头插入校验逻辑，调用 `_validate_sql_safety(sql)`
2. `_validate_sql_safety(sql)` 函数：
   - 用 `sqlparse.parse(sql)` 解析 SQL 并格式化为标准形式
   - 定义黑名单关键词：`DROP, DELETE, UPDATE, INSERT, ALTER, CREATE, TRUNCATE, EXEC, EXECUTE, ATTACH, DETACH, PRAGMA, REINDEX, VACUUM`
   - 正则匹配 `\b(?:关键词)\b`（不区分大小写），匹配到任一则抛出 `ValueError("安全拦截: 不允许执行 {操作类型} 操作")`
   - 额外白名单检查：解析后的语句类型必须是 `SELECT`、`EXPLAIN`，或以 `WITH` 开头的 CTE SELECT
3. SQLite 连接添加超时：`conn.execute("PRAGMA query_only = OFF")` 等，但主要通过代码层校验
4. 在 `execute_sql()` 中查询后限制返回行数：超过 1000 行时只返回前 1000 行，并 `print(f"结果已截断: {original_count} → 1000 行")`
5. 为连接设置 busy_timeout: `conn.execute("PRAGMA busy_timeout = 5000")`

**验证**：
```python
# 在 backend 目录运行
python -c "
from app.nl2sql.database import execute_sql
# 应成功
rows, cols = execute_sql('SELECT COUNT(*) FROM [orders]')
print('SELECT OK:', rows)
# 应抛出异常
try:
    execute_sql('DROP TABLE orders')
except ValueError as e:
    print('DROP blocked:', e)
try:
    execute_sql('DELETE FROM orders')
except ValueError as e:
    print('DELETE blocked:', e)
"
```

---

### 任务 A2：结构化错误处理体系

**目标**：建立错误码枚举，统一后端异常响应格式，让前端能根据错误码做差异化展示。

**新建文件**：`backend/app/exceptions.py`

**内容要求**：
```python
from enum import Enum

class ErrorCode(str, Enum):
    SQL_GENERATION_FAILED = "SQL_GENERATION_FAILED"
    SQL_EXECUTION_ERROR = "SQL_EXECUTION_ERROR"
    SQL_EMPTY_RESULT = "SQL_EMPTY_RESULT"
    SQL_TIMEOUT = "SQL_TIMEOUT"
    SAFETY_VIOLATION = "SAFETY_VIOLATION"
    LLM_SERVICE_ERROR = "LLM_SERVICE_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    INVALID_REQUEST = "INVALID_REQUEST"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    UNSUPPORTED_FILE_TYPE = "UNSUPPORTED_FILE_TYPE"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    VECTOR_STORE_ERROR = "VECTOR_STORE_ERROR"

# 错误码 -> 用户友好消息
ERROR_MESSAGES = { ... }

# 异常 -> 错误码 映射函数
def classify_exception(e: Exception) -> ErrorCode: ...
```

**修改文件**：`backend/app/models/schemas.py`

在文件末尾追加：
```python
class ErrorResponse(BaseModel):
    error_code: str
    message: str
    detail: Optional[str] = None
```

**修改文件**：`backend/app/routes/chat.py`

在 `/api/chat` 和 `/api/chat/stream` 的异常处理中，替换笼统的 `HTTPException(500)`：
- 导入 `from app.exceptions import ErrorCode, ERROR_MESSAGES, classify_exception`
- 根据异常类型映射到对应 ErrorCode
- 返回 `HTTPException(status_code=对应状态码, detail=ErrorResponse(...).model_dump())`
- 原始错误信息截断到 200 字符（防止敏感信息泄露）
- SQL 结果为空不算错误，正常返回 200 但 answer 说明"未找到匹配数据"

**验证**：
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "删除所有订单"}'
# 应返回 500 + error_code: SAFETY_VIOLATION
```

---

### 任务 A3：查询缓存层

**目标**：对相同问题缓存 SQL 查询结果，减少重复的 LLM 调用和数据库查询。

**新建文件**：`backend/app/services/cache.py`

**实现要点**：
1. 使用 `cachetools.TTLCache` 或自己实现一个基于时间和容量的内存缓存
2. 缓存 Key = `md5(question.lower().strip())[:16]`（问题归一化后取 hash）
3. 缓存 Value = `{"sql": str, "columns": list, "rows": list, "answer": str, "timestamp": float}`
4. 配置：
   - `CACHE_MAX_SIZE = 500`（最多缓存 500 条）
   - `CACHE_TTL = 1800`（30 分钟过期）
   - 在 `config.py` 中追加这两个配置项
5. 提供三个函数：
   - `get_cache(question: str) -> dict | None`
   - `set_cache(question: str, result: dict) -> None`
   - `clear_cache() -> int`（返回清除条数）
   - `get_cache_stats() -> dict`（返回缓存命中率等统计）

**修改文件**：`backend/app/nl2sql/database.py`

在 `execute_sql()` 函数开头检查缓存，命中则直接返回并打印 `[Cache Hit]`：
```python
from app.services.cache import get_cache
cached = get_cache(sql)  # 用 SQL 文本做 key
if cached:
    print(f"  [Cache Hit] 命中缓存")
    return cached["rows"], cached["columns"]
```

（注意：这里缓存 SQL 结果而非问题，因为在 database.py 中只能拿到 SQL。最终答案层的缓存在 pipeline 中做。）

**修改文件**：`backend/app/nl2sql/pipeline.py`

在 `query()` 方法开头，在 RAG 检索前先检查问题级缓存：
```python
from app.services.cache import get_cache, set_cache
cached = get_cache(question)
if cached:
    print(f"  [Cache Hit] 问题: {question[:50]}...")
    return build_cached_response(cached, conv_id)
```

执行完成后，调用 `set_cache(question, {...})` 缓存结果。

**验证**：
```python
# 第一次查询 -> 无缓存
# 第二次相同查询 -> 应在日志中看到 [Cache Hit]，响应时间显著缩短
```

---

### 任务 A4：API 限流中间件

**目标**：保护后端 API 不被滥用，限制单 IP 的请求频率。

**新建文件**：`backend/app/middleware/rate_limit.py`

**实现要点**：
1. 使用 `collections.defaultdict` + `time` 实现滑动窗口限流（无需额外依赖）
2. 可配置参数（在 `config.py` 追加）：
   - `RATE_LIMIT_MAX_REQUESTS = 60`（每分钟 60 次）
   - `RATE_LIMIT_WINDOW_SECONDS = 60`（窗口 60 秒）
3. 使用客户 IP（`request.client.host` 或 `X-Forwarded-For` header）
4. 超限时返回 429 状态码 + `ErrorResponse(error_code="RATE_LIMIT_EXCEEDED", ...)`
5. 用 `asyncio.Lock` 保证线程安全
6. 定期清理过期记录（每 5 分钟清理一次）

**修改文件**：`backend/app/main.py`

在 `app = FastAPI(...)` 之后添加：
```python
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # 调用 rate_limit 检查
    # 超限返回 429
    # 否则继续
```

**验证**：
```bash
# 快速连续发 60+ 次请求
for i in {1..65}; do curl -s http://localhost:8000/api/health; done
# 后几次应返回 429
```

---

### 任务 A5：单元测试

**目标**：为核心模块建立测试覆盖。

**新建文件及测试内容**：

#### `backend/tests/__init__.py`（空文件）

#### `backend/tests/conftest.py`
```python
import pytest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

@pytest.fixture
def test_db():
    """创建测试数据库"""
    from app.nl2sql.database import init_database
    import tempfile
    # 用临时路径初始化数据库
    ...
```

#### `backend/tests/test_database.py`
至少 8 个测试用例：
1. `test_init_database_creates_tables` — 验证 5 张表都被创建
2. `test_execute_select_success` — 正常 SELECT 查询
3. `test_sql_safety_blocks_drop` — DROP 被拦截
4. `test_sql_safety_blocks_delete` — DELETE 被拦截
5. `test_sql_safety_blocks_insert` — INSERT 被拦截
6. `test_sql_safety_allows_select` — SELECT 正常通过
7. `test_sql_safety_allows_with_cte` — WITH CTE SELECT 正常通过
8. `test_get_schema_info_returns_all_tables` — Schema 信息包含 5 表

#### `backend/tests/test_translator.py`
至少 5 个测试用例：
1. `test_translate_simple_question` — 简单聚合查询
2. `test_translate_join_question` — JOIN 查询
3. `test_translate_returns_only_sql` — 返回纯净 SQL
4. `test_invalid_sql_detected` — CANNOT_TRANSLATE 被识别
5. `test_sql_is_cleaned` — Markdown ``` 包裹被清理

**运行测试**：
```bash
cd backend
pip install pytest pytest-asyncio httpx
python -m pytest tests/ -v
```

---

## 执行顺序建议

```
第 1 周: A1(SQL安全) → A2(错误处理)
第 2 周: A3(缓存层) → A5(单元测试-数据库)
第 3 周: A4(限流) → A5(单元测试-翻译器)
第 4 周: 整体联调、补充边界case
```

也可完全并行执行 A1~A5（它们修改不同函数/文件），最后统一验证。

---

## 验收标准

1. 所有危险 SQL 操作被拦截
2. 所有 API 异常返回统一 ErrorResponse 格式
3. 相同问题第二次查询在 200ms 内返回（缓存命中）
4. 单 IP 超过 60 次/分钟返回 429
5. `pytest tests/ -v` 全部通过（至少 13 个测试）

## 启动提示词

将此文档内容发送给 AI：

```
请严格按照本文档执行开发任务，按 A1→A2→A3→A4→A5 顺序完成。
每完成一个任务，运行对应的验证命令确认通过后再继续。
所有修改仅限后端文件，不要动前端代码。
完成后运行 pytest 验证。
```
