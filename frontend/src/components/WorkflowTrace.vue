<template>
  <div class="workflow-trace" v-if="hasWorkflow">
    <button class="trace-toggle" @click="expanded = !expanded">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polyline points="9 11 12 14 22 4"/>
        <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
      </svg>
      智能问数流程追踪
      <svg
        class="chevron"
        :class="{ rotated: expanded }"
        width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
      >
        <polyline points="6 9 12 15 18 9"/>
      </svg>
    </button>

    <div v-if="expanded" class="trace-body slide-in">
      <!-- 步骤导航栏 -->
      <div class="step-nav">
        <button
          v-for="(step, idx) in steps"
          :key="idx"
          class="step-tab"
          :class="{ active: activeStep === idx, done: step.status === 'done', error: step.status === 'error' }"
          @click="activeStep = idx"
        >
          <span class="step-num">{{ idx + 1 }}</span>
          <span class="step-name">{{ step.label }}</span>
        </button>
      </div>

      <!-- 当前步骤详情 -->
      <div class="step-detail">
        <!-- Step 0: 用户提问 -->
        <div v-if="activeStep === 0" class="detail-card">
          <div class="detail-card-header">
            <span class="dc-icon user-icon">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>
              </svg>
            </span>
            <div>
              <div class="dc-title">用户提问</div>
              <div class="dc-subtitle">接收到的问题原文</div>
            </div>
            <span class="dc-badge badge-intent">NL2SQL 入口</span>
          </div>
          <div class="detail-card-body">
            <div class="question-display">{{ message.question || '（未记录）' }}</div>
          </div>
        </div>

        <!-- Step 1: Schema 匹配 -->
        <div v-if="activeStep === 1" class="detail-card">
          <div class="detail-card-header">
            <span class="dc-icon schema-icon">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
              </svg>
            </span>
            <div>
              <div class="dc-title">Schema 匹配</div>
              <div class="dc-subtitle">识别目标数据表与字段</div>
            </div>
            <span class="dc-badge badge-schema">RAG 辅助检索</span>
          </div>
          <div class="detail-card-body">
            <div class="kv-row">
              <span class="kv-key">匹配表</span>
              <code class="kv-code">{{ matchedTable }}</code>
            </div>
            <div class="kv-row" v-if="matchedColumns.length">
              <span class="kv-key">查询字段</span>
              <span class="kv-value">{{ matchedColumns.join('、') }}</span>
            </div>
            <div class="kv-row" v-if="message.sources?.length">
              <span class="kv-key">RAG 参考</span>
              <span class="kv-value">{{ message.sources.length }} 个相关文档片段</span>
            </div>
            <div v-if="message.sources?.length" class="rag-docs">
              <div class="rag-docs-title">相关文档内容</div>
              <div v-for="(doc, di) in message.sources" :key="di" class="rag-doc-item">
                <div class="rag-doc-header">
                  <span class="rag-doc-num">#{{ di + 1 }}</span>
                  <span class="rag-doc-source" v-if="doc.source">{{ doc.source }}</span>
                  <span class="rag-doc-score" v-if="doc.score !== null && doc.score !== undefined">
                    相似度: {{ (doc.score * 100).toFixed(1) }}%
                  </span>
                </div>
                <div class="rag-doc-content">{{ doc.content }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- Step 2: NL2SQL 翻译 -->
        <div v-if="activeStep === 2" class="detail-card">
          <div class="detail-card-header">
            <span class="dc-icon llm-icon">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>
              </svg>
            </span>
            <div>
              <div class="dc-title">NL2SQL 翻译</div>
              <div class="dc-subtitle">自然语言 → SQL 语句</div>
            </div>
            <span class="dc-badge badge-llm">DeepSeek 大模型</span>
          </div>
          <div class="detail-card-body">
            <div class="sql-block">
              <div class="sql-block-header">
                <span class="sql-label">生成的 SQL</span>
                <button class="btn-copy" @click="copySQL" title="复制 SQL">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                  </svg>
                  复制
                </button>
              </div>
              <pre class="sql-code"><code>{{ message.sql }}</code></pre>
            </div>
          </div>
        </div>

        <!-- Step 3: SQL 执行 -->
        <div v-if="activeStep === 3" class="detail-card">
          <div class="detail-card-header">
            <span class="dc-icon db-icon">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
              </svg>
            </span>
            <div>
              <div class="dc-title">SQL 执行</div>
              <div class="dc-subtitle">SQLite 引擎执行查询</div>
            </div>
            <span class="dc-badge badge-db">SQLite</span>
          </div>
          <div class="detail-card-body">
            <div class="exec-stats">
              <div class="exec-stat">
                <span class="stat-num">{{ sqlResult?.row_count || 0 }}</span>
                <span class="stat-label">返回行数</span>
              </div>
              <div class="exec-stat">
                <span class="stat-num">{{ (sqlResult?.columns || []).length }}</span>
                <span class="stat-label">返回列数</span>
              </div>
            </div>
            <div class="kv-row" v-if="sqlResult?.columns">
              <span class="kv-key">字段列表</span>
              <span class="kv-value">{{ sqlResult.columns.join('、') }}</span>
            </div>
            <div class="result-table-wrap" v-if="sqlResult?.rows?.length">
              <table>
                <thead>
                  <tr>
                    <th v-for="col in sqlResult.columns.slice(0, 4)" :key="col">{{ col }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(row, ri) in sqlResult.rows.slice(0, 5)" :key="ri">
                    <td v-for="col in sqlResult.columns.slice(0, 4)" :key="col">
                      {{ formatValue(row[col]) }}
                    </td>
                  </tr>
                </tbody>
              </table>
              <div class="table-foot" v-if="sqlResult.rows.length > 5">
                仅显示前 5 行，共 {{ sqlResult.rows.length }} 行
              </div>
            </div>
          </div>
        </div>

        <!-- Step 4: 结果呈现 -->
        <div v-if="activeStep === 4" class="detail-card">
          <div class="detail-card-header">
            <span class="dc-icon answer-icon">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>
              </svg>
            </span>
            <div>
              <div class="dc-title">结果呈现</div>
              <div class="dc-subtitle">LLM 生成自然语言回答</div>
            </div>
            <span class="dc-badge badge-answer">LLM 回答</span>
          </div>
          <div class="detail-card-body">
            <div class="kv-row">
              <span class="kv-key">数据可视化</span>
              <span class="kv-value" :class="{ 'text-success': message.chartData, 'text-muted': !message.chartData }">
                <template v-if="message.chartData">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="20 6 9 17 4 12"/>
                  </svg>
                  已生成 {{ message.chartData.type === 'bar' ? '柱状图' : message.chartData.type === 'line' ? '折线图' : message.chartData.type === 'pie' ? '饼图' : '图表' }}
                </template>
                <template v-else>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                  </svg>
                  未生成图表
                </template>
              </span>
            </div>
            <div class="kv-row">
              <span class="kv-key">响应耗时</span>
              <span class="kv-value highlight">{{ message.responseTimeMs || '?' }} ms</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  message: { type: Object, required: true },
})

const expanded = ref(false)
const activeStep = ref(0)

const sqlResult = computed(() => props.message.sqlResult)
const hasWorkflow = computed(() => !!props.message.sql)

const steps = [
  { label: '提问', status: 'done' },
  { label: 'Schema匹配', status: 'done' },
  { label: 'NL2SQL翻译', status: 'done' },
  { label: 'SQL执行', status: 'done' },
  { label: '结果呈现', status: 'done' },
]

const matchedTable = computed(() => {
  const sql = props.message.sql || ''
  const match = sql.match(/FROM\s+\[(\w+)\]/i)
  return match ? match[1] : '自动匹配'
})

const matchedColumns = computed(() => {
  const sql = props.message.sql || ''
  const matches = sql.match(/SELECT\s+(.+?)\s+FROM/i)
  if (!matches) return []
  const cols = matches[1]
  if (cols.trim() === '*') return ['全部列']
  return cols.split(',').map(c => c.trim().replace(/[\[\]]/g, ''))
})

function formatValue(val) {
  if (val === null || val === undefined) return '-'
  if (typeof val === 'number') {
    return Number.isInteger(val) ? val.toLocaleString() : val.toFixed(2)
  }
  return String(val)
}

function copySQL() {
  navigator.clipboard.writeText(props.message.sql || '')
}
</script>

<style scoped>
.workflow-trace {
  margin-top: 14px;
}

.trace-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: none;
  border: none;
  color: var(--primary);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  padding: 4px 0;
  transition: color var(--transition);
}

.trace-toggle:hover {
  color: #4338ca;
}

.chevron {
  transition: transform 0.2s;
}

.chevron.rotated {
  transform: rotate(180deg);
}

.trace-body {
  margin-top: 10px;
}

/* ===== 步骤导航栏 ===== */
.step-nav {
  display: flex;
  gap: 0;
  background: #f8fafc;
  border: 1px solid var(--border);
  border-radius: 10px;
  overflow: hidden;
}

.step-tab {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px 8px;
  background: transparent;
  border: none;
  border-right: 1px solid #e2e8f0;
  cursor: pointer;
  color: #94a3b8;
  font-size: 12px;
  font-weight: 500;
  transition: all 0.2s;
  position: relative;
}

.step-tab:last-child {
  border-right: none;
}

.step-tab:hover {
  background: #f1f5f9;
  color: #64748b;
}

.step-tab.active {
  background: #fff;
  color: var(--primary);
  font-weight: 600;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}

.step-tab.active::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 12px;
  right: 12px;
  height: 2px;
  background: var(--primary);
  border-radius: 1px;
}

.step-num {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #e2e8f0;
  color: #94a3b8;
  font-size: 11px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  flex-shrink: 0;
}

.step-tab.active .step-num {
  background: var(--primary);
  color: #fff;
}

.step-name {
  white-space: nowrap;
}

/* ===== 步骤详情卡片 ===== */
.step-detail {
  margin-top: 10px;
}

.detail-card {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 10px;
  overflow: hidden;
}

.detail-card-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  background: #fafbfc;
  border-bottom: 1px solid #f1f5f9;
}

.dc-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.user-icon { background: #ede9fe; color: #7c3aed; }
.schema-icon { background: #e0f2fe; color: #0284c7; }
.llm-icon { background: #fef3c7; color: #d97706; }
.db-icon { background: #fce7f3; color: #db2777; }
.answer-icon { background: #ecfdf5; color: #059669; }

.dc-title {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
}

.dc-subtitle {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 1px;
}

.dc-badge {
  margin-left: auto;
  font-size: 10px;
  padding: 3px 10px;
  border-radius: 12px;
  font-weight: 500;
  flex-shrink: 0;
}

.badge-intent { background: #ede9fe; color: #7c3aed; }
.badge-schema { background: #e0f2fe; color: #0284c7; }
.badge-llm { background: #fef3c7; color: #d97706; }
.badge-db { background: #fce7f3; color: #db2777; }
.badge-answer { background: #ecfdf5; color: #059669; }

.detail-card-body {
  padding: 16px;
}

/* 提问文本 */
.question-display {
  font-size: 14px;
  color: #1e293b;
  line-height: 1.7;
  background: #f8fafc;
  border-radius: 8px;
  padding: 12px 14px;
  border-left: 3px solid var(--primary);
}

/* KV 信息行 */
.kv-row {
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding: 8px 0;
  font-size: 13px;
}

.kv-row + .kv-row {
  border-top: 1px solid #f8fafc;
}

.kv-key {
  color: #94a3b8;
  min-width: 60px;
  flex-shrink: 0;
}

.kv-value {
  color: #334155;
}

.kv-value.highlight {
  color: var(--primary);
  font-weight: 600;
}

.kv-value.text-success {
  color: var(--success);
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.kv-value.text-muted {
  color: #94a3b8;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.kv-code {
  background: #f1f5f9;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-family: 'SF Mono', 'Fira Code', monospace;
  color: var(--primary);
}

/* 执行统计 */
.exec-stats {
  display: flex;
  gap: 16px;
  margin-bottom: 12px;
}

.exec-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 10px 20px;
  background: #f8fafc;
  border-radius: 8px;
  border: 1px solid #f1f5f9;
}

.stat-num {
  font-size: 22px;
  font-weight: 700;
  color: var(--primary);
}

.stat-label {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 2px;
}

/* SQL 代码块 */
.sql-block {
  margin: 0;
}

.sql-block-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.sql-label {
  font-size: 12px;
  color: #64748b;
  font-weight: 500;
}

.btn-copy {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 5px;
  padding: 3px 10px;
  cursor: pointer;
  font-size: 11px;
  color: #64748b;
  transition: all 0.15s;
}

.btn-copy:hover {
  border-color: var(--primary);
  color: var(--primary);
  background: #f8fafc;
}

.sql-code {
  background: #1e293b;
  color: #e2e8f0;
  padding: 14px 16px;
  border-radius: 8px;
  font-size: 13px;
  line-height: 1.8;
  overflow-x: auto;
  margin: 0;
  font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
}

.sql-code code {
  background: none;
  padding: 0;
  color: inherit;
  font-size: inherit;
}

/* 结果表格 */
.result-table-wrap {
  margin-top: 8px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  overflow: hidden;
}

.result-table-wrap table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.result-table-wrap th {
  background: #f8fafc;
  padding: 8px 12px;
  text-align: left;
  font-weight: 600;
  color: #475569;
  border-bottom: 1px solid #e2e8f0;
  white-space: nowrap;
}

.result-table-wrap td {
  padding: 7px 12px;
  border-bottom: 1px solid #f1f5f9;
  color: #334155;
}

.result-table-wrap tr:last-child td {
  border-bottom: none;
}

.table-foot {
  font-size: 11px;
  color: #94a3b8;
  text-align: center;
  padding: 8px;
  background: #fafbfc;
  border-top: 1px solid #f1f5f9;
}

/* RAG 文档展示 */
.rag-docs {
  margin-top: 10px;
  border-top: 1px solid #f1f5f9;
  padding-top: 10px;
}

.rag-docs-title {
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  margin-bottom: 8px;
}

.rag-doc-item {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 8px;
}

.rag-doc-item:last-child {
  margin-bottom: 0;
}

.rag-doc-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
  flex-wrap: wrap;
}

.rag-doc-num {
  font-size: 11px;
  font-weight: 700;
  color: var(--primary);
  background: #eef2ff;
  padding: 1px 7px;
  border-radius: 4px;
}

.rag-doc-source {
  font-size: 11px;
  color: #94a3b8;
  font-family: 'SF Mono', 'Fira Code', monospace;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 200px;
}

.rag-doc-score {
  font-size: 11px;
  color: #059669;
  background: #ecfdf5;
  padding: 1px 7px;
  border-radius: 4px;
  margin-left: auto;
}

.rag-doc-content {
  font-size: 12px;
  color: #475569;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

/* 响应式：小屏幕堆叠步骤 */
@media (max-width: 640px) {
  .step-nav {
    flex-wrap: wrap;
  }
  .step-tab {
    flex: 1 1 auto;
    min-width: 60px;
    padding: 8px 6px;
    font-size: 11px;
  }
  .step-name {
    display: none;
  }
  .step-num {
    width: 18px;
    height: 18px;
    font-size: 10px;
  }
}
</style>