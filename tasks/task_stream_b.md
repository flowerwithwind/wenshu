# AI 开发任务书 — 工作流 B：数据与对话管理层

> **目标**：让用户能自行上传数据、导出结果，对话持久化，在线管理知识库  
> **工期**：约 4 周  
> **涉及文件**：后端新建 7 个文件，前端新建 2 个组件，修改 `chat.py` 和 `main.py`  
> **不与工作流 A/C 冲突**（除 main.py 追加路由的简单合并）  
> **启动指令**：将本文档直接喂给 AI，说"按此文档执行开发"

---

## 项目环境

- **项目根目录**: `c:\Users\zhy\Desktop\wenshu`
- **后端**: Python 3.10+ / FastAPI / SQLite
- **前端**: Vue 3 + Pinia + Chart.js + 原生 CSS
- **后端启动**: `cd backend && python -m app.main`
- **前端启动**: `cd frontend && npm run dev`

---

## 关键参考代码

### 数据库建表逻辑 (`backend/app/nl2sql/database.py`)

已有的核心函数：
```python
def infer_sql_type(values: List[str]) -> str:  # 推断 INTEGER/REAL/TEXT
def init_database(db_path):                     # 从 CSV 文件建表
def get_schema_info(db_path) -> str:            # 获取所有表 Schema
def execute_sql(sql, db_path) -> tuple:         # 执行查询
CSV_TABLE_MAP = { ... }                         # CSV文件→表名映射
```

### 路由注册方式 (`backend/app/main.py`)

```python
from app.routes.chat import router as chat_router
app.include_router(chat_router)
# 新路由在这里追加
```

### 前端 API 调用 (`frontend/src/api/index.js`)

```javascript
import axios from 'axios'
const api = axios.create({ baseURL: '/api', timeout: 60000 })
// 此处追加新 API 函数
export { api }
```

### 前端路由 (`frontend/src/main.js`)

```javascript
const routes = [{ path: '/', component: Home }]
// 此处追加新路由
```

### 前端 Home.vue 结构

侧边栏(`.sidebar`) + 主内容区(`.main-content`)：
- 侧边栏顶部：logo + 新对话按钮(`.btn-new-chat`) + 历史列表(`.history-list`)
- 主内容区：topbar + chat-area + input-area

**CSS 变量**（`frontend/src/style.css` 中定义）：
```css
--primary: #4f46e5
--primary-hover: #4338ca
--primary-light: #eef2ff
--bg: #f8fafc
--bg-card: #ffffff
--bg-sidebar: #1e293b
--border: #e2e8f0
--text: #1e293b
--text-secondary: #64748b
--success: #10b981
--danger: #ef4444
--radius-sm: 8px
--shadow-lg: 0 10px 25px rgba(0,0,0,0.1)
--transition: 0.2s ease
```

---

## 任务清单

### 任务 B1：文件上传功能（后端 + 前端）

**目标**：用户可上传 CSV/Excel 文件，自动建表并入 SQLite，重建向量索引。

#### 后端部分

**新建 `backend/app/services/file_upload.py`**：

```python
"""文件上传服务：解析 CSV/Excel → 写入 SQLite → 更新 CSV_TABLE_MAP"""
import os, csv, re
from typing import List, Dict, Tuple
import pandas as pd  # openpyxl 由 pandas 自动调用

from app.config import DATASET_DIR, MAX_UPLOAD_SIZE_MB
from app.nl2sql.database import CSV_TABLE_MAP, init_database, DB_PATH

ALLOWED_EXTENSIONS = {'.csv', '.xlsx', '.xls'}
MAX_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024

def validate_file(filename: str, size: int) -> str:
    """验证文件：检查扩展名、大小。返回错误信息或空字符串"""
    ...

def sanitize_table_name(filename: str) -> str:
    """从文件名生成安全的表名：去扩展名、替换特殊字符为_、限制长度"""
    name = os.path.splitext(filename)[0]
    name = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fff_]', '_', name)
    return name[:50]

def save_uploaded_file(upload_file, target_dir: str = None) -> str:
    """保存上传文件到 datasets/ 目录，返回保存的完整路径"""
    ...

def import_to_database(file_path: str, table_name: str) -> Dict:
    """
    将 CSV/Excel 导入 SQLite：
    1. pandas 读取文件
    2. 推断列类型（复用 database.infer_sql_type 逻辑）
    3. DROP TABLE IF EXISTS → CREATE TABLE → 批量 INSERT
    4. 更新 CSV_TABLE_MAP
    5. 返回: {"table_name": str, "row_count": int, "columns": [str]}
    """
    ...
```

**新建 `backend/app/routes/upload.py`**：

```python
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from app.services.file_upload import validate_file, save_uploaded_file, import_to_database

upload_router = APIRouter(prefix="/api", tags=["upload"])

@upload_router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    table_name: str = Form(None)  # 用户可选表名
):
    """上传并导入 CSV/Excel 文件"""
    # 1. 读取内容验证大小
    content = await file.read()
    error = validate_file(file.filename, len(content))
    if error:
        raise HTTPException(400, detail=...)
    
    # 2. 保存到 datasets/
    tname = table_name or sanitize_table_name(file.filename)
    file_path = save_uploaded_file(...)
    
    # 3. 导入数据库
    result = import_to_database(file_path, tname)
    
    # 4. 重建向量索引（调用 rag pipeline）
    from app.rag.pipeline import get_pipeline
    pipeline = get_pipeline()
    chunks = pipeline.build_index()
    
    return {"status": "ok", "table_name": tname, "row_count": result["row_count"],
            "columns": result["columns"], "chunks_added": chunks}
```

**修改 `backend/app/main.py`**：
在 `app.include_router(chat_router)` 之后追加：
```python
from app.routes.upload import upload_router
app.include_router(upload_router)
```

#### 前端部分

**新建 `frontend/src/components/FileUpload.vue`**：

- 拖拽上传区域：虚线边框 `2px dashed var(--primary)`，支持 `@dragover` / `@drop` / `@click` 选择文件
- 点击触发隐藏的 `<input type="file" accept=".csv,.xlsx,.xls">`
- 上传时显示进度条（使用 axios `onUploadProgress`）
- 成功显示绿色提示：`✅ 已导入表 [xxx]，共 N 行 M 列` + 建议问题
- 失败显示红色提示：错误信息
- 样式与现有深色主题一致
- 上传 API：`POST /api/upload`，FormData 格式

**修改 `frontend/src/views/Home.vue`**（可选集成）：
- 在侧边栏 `.history-label` 下方添加 `<FileUpload />` 组件的插槽
- 或在 topbar 中添加上传图标按钮，点击弹出上传对话框

**修改 `frontend/src/api/index.js`**，追加：
```javascript
export const uploadFile = (file, tableName = null) => {
  const formData = new FormData()
  formData.append('file', file)
  if (tableName) formData.append('table_name', tableName)
  return api.post('/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  })
}
```

---

### 任务 B2：对话持久化（内存 → SQLite）

**目标**：将 `conversation_store` 从内存 dict 迁移到 SQLite + 文件 JSON 混合存储。

**新建 `backend/app/services/conversation_store.py`**：

```python
"""对话持久化存储 — JSON 文件 + SQLite 索引"""
import os, json, uuid, time
from typing import List, Dict, Optional

STORAGE_DIR = os.path.join(os.path.dirname(__file__), '../../data/conversations')

class ConversationStore:
    def __init__(self):
        os.makedirs(STORAGE_DIR, exist_ok=True)
        # 对话元数据索引（SQLite 或 JSON）
        self._load_index()
    
    def create(self, messages: List[Dict]) -> str:  # 返回 conv_id
    def add_message(self, conv_id: str, msg: Dict) -> None:
    def update_last_message(self, conv_id: str, msg: Dict) -> None:
    def get(self, conv_id: str) -> Optional[Dict]:
    def list_all(self) -> List[Dict]:
    def delete(self, conv_id: str) -> bool:
    def clear(self) -> int:

# 全局单例
_store = None
def get_conversation_store() -> ConversationStore:
    global _store
    if _store is None: _store = ConversationStore()
    return _store
```

**修改 `backend/app/routes/chat.py`**：

将 `conversation_store: dict = {}` 替换为：
```python
from app.services.conversation_store import get_conversation_store
```

不再手动 `conversation_store[conv_id] = []`，改为调用 `get_conversation_store().add_message(conv_id, {...})`。

所有 `/history` 相关端点改为从 `get_conversation_store()` 读取。

**存储格式**（每个对话一个 JSON 文件）：
```json
{
  "conversation_id": "uuid",
  "created_at": "2026-06-07T10:00:00",
  "updated_at": "2026-06-07T10:05:00",
  "messages": [
    {"id": "1", "role": "user", "question": "...", "timestamp": "..."},
    {"id": "2", "role": "assistant", "answer": "...", "sql": "...", "sources": [...], "timestamp": "..."}
  ]
}
```

---

### 任务 B3：查询结果导出

**目标**：支持将 SQL 查询结果导出为 Excel/CSV，将图表导出为 PNG。

**新建 `backend/app/services/export_service.py`**：

```python
"""数据导出服务"""
import io, csv
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment

def export_to_csv(columns: list, rows: list) -> bytes:
    """将查询结果导出为 CSV 字节流"""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(columns)
    for row in rows:
        writer.writerow([row.get(col, '') for col in columns])
    return output.getvalue().encode('utf-8-sig')

def export_to_excel(columns: list, rows: list, sheet_name: str = "查询结果") -> bytes:
    """将查询结果导出为格式化的 Excel 文件"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_name
    # 表头加粗+背景色
    header_fill = PatternFill(start_color="4F46E5", end_color="4F46E5", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    ...
    return buffer.getvalue()
```

**新建 `backend/app/routes/export.py`**：

```python
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from app.services.export_service import export_to_csv, export_to_excel

export_router = APIRouter(prefix="/api", tags=["export"])

@export_router.get("/export")
async def export_result(
    conversation_id: str = Query(...),
    message_id: str = Query(...),
    format: str = Query("csv"),  # csv 或 xlsx
):
    """导出指定对话中某条消息的查询结果"""
    store = get_conversation_store()
    conv = store.get(conversation_id)
    # 找到对应消息，提取 sql_result
    ...
    if format == "xlsx":
        data = export_to_excel(result["columns"], result["rows"])
        return Response(data, media_type="...")
    else:
        data = export_to_csv(result["columns"], result["rows"])
        return Response(data, media_type="text/csv", headers={...})
```

**前端修改**：在 `ChatMessage.vue` 的 SQL 结果展示区域添加导出按钮：
```html
<button v-if="message.sqlResult" class="btn-export" @click="exportResult('csv')">
  <svg>...</svg> 导出CSV
</button>
<button v-if="message.sqlResult" class="btn-export" @click="exportResult('xlsx')">
  <svg>...</svg> 导出Excel
</button>
```

```javascript
async function exportResult(format) {
  const url = `/api/export?conversation_id=${store.currentConversationId}&message_id=${props.message.id}&format=${format}`
  window.open(url, '_blank')
}
```

**修改 `frontend/src/views/Home.vue`**：在 topbar-actions 区域添加导出按钮。

---

### 任务 B4：知识库在线管理

**目标**：前端 UI 管理 NL2SQL 知识库（增删改 Few-shot 示例、同义词、领域映射）。

**新建 `backend/app/services/knowledge_manager.py`**：

```python
"""NL2SQL 知识库 CRUD 管理"""
import json
from typing import List, Dict

KNOWLEDGE_PATH = os.path.join(DATASET_DIR, "nl2sql_knowledge.json")

def load_knowledge() -> Dict:
    with open(KNOWLEDGE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_knowledge(data: Dict) -> None:
    with open(KNOWLEDGE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def add_example(question: str, sql: str, tables: List[str], tags: List[str]) -> Dict:
    """添加一条 Few-shot 示例"""

def delete_example(index: int) -> bool:
    """删除指定索引的示例"""

def update_example(index: int, **kwargs) -> Dict:
    """更新一条示例"""

def add_synonym(synonyms: List[str], target_column: str, table: str) -> Dict:
    """添加同义词映射"""

def add_domain_mapping(term: str, mapping: str, table: str) -> Dict:
    """添加领域术语映射"""

def get_stats() -> Dict:
    """知识库统计: 示例数、同义词数、领域映射数、表数"""
```

**新建管理路由**（追加到 upload 路由或新建 `backend/app/routes/knowledge.py`）：

```python
from fastapi import APIRouter
from app.services.knowledge_manager import (
    load_knowledge, add_example, delete_example, update_example,
    add_synonym, add_domain_mapping, get_stats
)

knowledge_router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])

@knowledge_router.get("/")
async def get_knowledge():  # 获取完整知识库（JSON）

@knowledge_router.get("/stats")
async def knowledge_stats():  # 获取统计

@knowledge_router.post("/examples")
async def create_example(...):  # 新增示例

@knowledge_router.put("/examples/{index}")
async def update_example(index: int, ...):  # 更新

@knowledge_router.delete("/examples/{index}")
async def delete_example(index: int):  # 删除

@knowledge_router.post("/synonyms")
async def create_synonym(...):  # 新增同义词

@knowledge_router.delete("/synonyms/{index}")
async def delete_synonym(index: int):  # 删除同义词
```

**新建 `frontend/src/components/KnowledgeManager.vue`**：

- 标签页切换："Few-shot 示例" / "同义词映射" / "领域映射" / "统计"
- "Few-shot 示例" 页：表格展示所有示例（问题、SQL、关联表、标签），行内编辑 + 删除按钮，顶部新建按钮
- "同义词映射" 页：卡片展示每组同义词→列名，可增删
- "领域映射" 页：表格展示术语→SQL映射，可增删
- "统计" 页：卡片展示总数统计
- 样式与现有深色主题一致
- 作为侧边栏或独立面板展示

**修改 `frontend/src/main.js`**：
```javascript
import KnowledgeManager from './components/KnowledgeManager.vue'

// 可选：作为弹窗面板，或在 Home.vue 侧边栏添加入口
```

**修改 `frontend/src/views/Home.vue`**：
在侧边栏的 `.history-label` 后添加"知识库管理"按钮，点击弹出 KnowledgeManager 面板。

---

## 执行顺序建议

```
第 1 周：B1(文件上传后端) → B1(前端FileUpload组件)
第 2 周：B2(对话持久化) → 迁移 chat.py
第 3 周：B3(导出后端) → B3(前端导出按钮)
第 4 周：B4(知识库管理后端+前端)
```

---

## 验收标准

1. 上传 CSV 文件后系统能识别新表并回答相关问题
2. 对话历史在服务重启后仍然保留
3. 能导出查询结果为 CSV 和 Excel 文件，Excel 带格式化表头
4. 知识库在线新增的 Few-shot 示例在下次提问中生效

## 启动提示词

```
请严格按照本文档执行开发任务，按 B1→B2→B3→B4 顺序完成。
每完成一个任务，运行对应的验证确认后再继续。
注意：
- 后端所有新建路由在 main.py 中注册时追加到已有路由之后
- 前端所有新建组件样式与现有深色主题保持一致，使用 --primary/#4f46e5 等 CSS 变量
- 不要修改工作流 A/C 负责的文件（database.py, translator.py, exceptions.py, cache.py, rate_limit.py）
```
