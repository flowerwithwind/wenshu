# SmartQA 项目规则

## 最高优先级规则

### 环境
- Python: conda 环境 `wenshu`
- Docker: 已启动可用
- 包安装: `pip install <pkg>` (在 wenshu 环境下)

### 开发准则
- 任何改动前先理解现有代码结构和风格
- 后端: FastAPI + LangChain，遵循已有模块划分（nl2sql/rag/agent/services/routes）
- 前端: Vue 3 + Pinia + Chart.js，遵循已有组件模式
- 测试: pytest，位置在 `backend/tests/`
- 所有新代码必须有完整类型注解
- 所有新功能必须有测试覆盖
- 日志使用结构化日志（loguru），不得使用 print
- API 变更必须同步更新前端

### 项目目标
该项目为求职用的 AI 应用开发工程师大型项目经历，代码质量、架构设计、可观测性、测试覆盖是核心关注点。
