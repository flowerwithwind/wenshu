<template>
  <div class="knowledge-manager" :class="{ embedded }">
    <header v-if="!embedded" class="km-header drawer">
      <h3>知识库管理</h3>
      <button class="km-close-btn" type="button" @click="$emit('close')">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </button>
    </header>

    <div class="km-tabs" role="tablist">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        type="button"
        class="km-tab"
        :class="{ active: activeTab === tab.key }"
        @click="activeTab = tab.key"
      >
        <span class="tab-label">{{ tab.label }}</span>
        <span v-if="tabCount(tab.key) !== null" class="tab-count">{{ tabCount(tab.key) }}</span>
      </button>
    </div>

    <!-- 概览 -->
    <div v-if="activeTab === 'stats'" class="km-panel">
      <div class="stats-grid">
        <div class="stat-card accent">
          <div class="stat-value">{{ stats.examples_count || 0 }}</div>
          <div class="stat-label">Few-shot 示例</div>
          <p class="stat-hint">提升 NL2SQL 生成准确率</p>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ stats.synonyms_count || 0 }}</div>
          <div class="stat-label">同义词映射</div>
          <p class="stat-hint">口语词 → 字段名</p>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ stats.domain_mappings_count || 0 }}</div>
          <div class="stat-label">领域映射</div>
          <p class="stat-hint">业务术语 → SQL 表达式</p>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ stats.table_schemas_count || 0 }}</div>
          <div class="stat-label">表 Schema</div>
          <p class="stat-hint">知识库中的表结构描述</p>
        </div>
      </div>

      <div class="intro-card">
        <h4>知识库如何参与问答</h4>
        <ul>
          <li><strong>Few-shot</strong>：相似问题-SQL 对会进入 Prompt，引导模型生成正确 SQL</li>
          <li><strong>同义词</strong>：用户说「成交额」可映射到「订单金额_元」等列</li>
          <li><strong>领域映射</strong>：如「高价值客户」映射为具体 WHERE 条件</li>
        </ul>
      </div>
    </div>

    <!-- Few-shot -->
    <div v-if="activeTab === 'examples'" class="km-panel">
      <div class="toolbar">
        <div>
          <h4>Few-shot 示例</h4>
          <p>维护「自然语言问题 → SQL」样例，支持标签与关联表</p>
        </div>
        <button type="button" class="km-add-btn" @click="showExampleForm = !showExampleForm">
          {{ showExampleForm ? '收起表单' : '+ 新增示例' }}
        </button>
      </div>

      <div v-if="showExampleForm" class="km-form">
        <div class="form-grid">
          <label class="field full">问题
            <input v-model="exampleForm.question" class="km-input" placeholder="例如：各省份销售额排名？" />
          </label>
          <label class="field full">SQL
            <textarea v-model="exampleForm.sql" class="km-textarea" rows="4" placeholder="SELECT ..." />
          </label>
          <label class="field">关联表
            <input v-model="exampleForm.tablesStr" class="km-input" placeholder="orders, products" />
          </label>
          <label class="field">标签
            <input v-model="exampleForm.tagsStr" class="km-input" placeholder="聚合, 排名" />
          </label>
        </div>
        <div class="km-form-actions">
          <button type="button" class="km-btn-save" @click="saveExample">保存</button>
          <button type="button" class="km-btn-cancel" @click="showExampleForm = false">取消</button>
        </div>
      </div>

      <div class="km-list cards">
        <article v-for="(ex, idx) in knowledge.question_sql_examples" :key="idx" class="km-item">
          <div class="km-item-header">
            <span class="km-item-index">#{{ idx + 1 }}</span>
            <span class="km-item-tags">
              <span v-for="tag in (ex.tags || [])" :key="tag" class="km-tag">{{ tag }}</span>
            </span>
            <button type="button" class="km-item-delete" @click="removeExample(idx)">删除</button>
          </div>
          <div class="km-item-body">
            <div class="km-item-label">问题</div>
            <div class="km-item-text">{{ ex.question }}</div>
            <div class="km-item-label">SQL</div>
            <pre class="km-item-sql">{{ ex.sql }}</pre>
            <div v-if="ex.tables?.length" class="km-item-meta">表：{{ ex.tables.join(', ') }}</div>
          </div>
        </article>
        <div v-if="!knowledge.question_sql_examples?.length" class="km-empty">暂无示例，点击右上角新增</div>
      </div>
    </div>

    <!-- 同义词 -->
    <div v-if="activeTab === 'synonyms'" class="km-panel">
      <div class="toolbar">
        <div>
          <h4>同义词映射</h4>
          <p>将用户口语映射到真实列名，减少字段识别错误</p>
        </div>
        <button type="button" class="km-add-btn" @click="showSynonymForm = !showSynonymForm">
          {{ showSynonymForm ? '收起表单' : '+ 新增同义词' }}
        </button>
      </div>

      <div v-if="showSynonymForm" class="km-form">
        <div class="form-grid">
          <label class="field full">同义词（逗号分隔）
            <input v-model="synonymForm.synonymsStr" class="km-input" placeholder="成交额, 销售金额, GMV" />
          </label>
          <label class="field">目标列名
            <input v-model="synonymForm.target_column" class="km-input" placeholder="订单金额_元" />
          </label>
          <label class="field">所属表
            <input v-model="synonymForm.table" class="km-input" placeholder="orders" />
          </label>
        </div>
        <div class="km-form-actions">
          <button type="button" class="km-btn-save" @click="saveSynonym">保存</button>
          <button type="button" class="km-btn-cancel" @click="showSynonymForm = false">取消</button>
        </div>
      </div>

      <div class="km-list cards">
        <article v-for="(syn, idx) in knowledge.synonym_mappings" :key="idx" class="km-item">
          <div class="km-item-header">
            <span class="km-item-index">#{{ idx + 1 }}</span>
            <span class="km-item-table">{{ syn.table }}.{{ syn.target_column }}</span>
            <button type="button" class="km-item-delete" @click="removeSynonym(idx)">删除</button>
          </div>
          <div class="km-item-body">
            <div class="km-item-tags">
              <span v-for="s in (syn.synonyms || [])" :key="s" class="km-tag">{{ s }}</span>
            </div>
          </div>
        </article>
        <div v-if="!knowledge.synonym_mappings?.length" class="km-empty">暂无同义词映射</div>
      </div>
    </div>

    <!-- 领域映射 -->
    <div v-if="activeTab === 'domain'" class="km-panel">
      <div class="toolbar">
        <div>
          <h4>领域映射</h4>
          <p>业务术语到 SQL 表达式的映射，如「高价值客户」</p>
        </div>
        <button type="button" class="km-add-btn" @click="showDomainForm = !showDomainForm">
          {{ showDomainForm ? '收起表单' : '+ 新增领域映射' }}
        </button>
      </div>

      <div v-if="showDomainForm" class="km-form">
        <div class="form-grid">
          <label class="field">术语
            <input v-model="domainForm.term" class="km-input" placeholder="高价值客户" />
          </label>
          <label class="field">适用表
            <input v-model="domainForm.table" class="km-input" placeholder="customers" />
          </label>
          <label class="field full">SQL 映射
            <input v-model="domainForm.mapping" class="km-input" placeholder="会员等级 IN ('金卡','钻石')" />
          </label>
        </div>
        <div class="km-form-actions">
          <button type="button" class="km-btn-save" @click="saveDomain">保存</button>
          <button type="button" class="km-btn-cancel" @click="showDomainForm = false">取消</button>
        </div>
      </div>

      <div class="km-list cards">
        <article v-for="(dm, idx) in knowledge.domain_mappings" :key="idx" class="km-item">
          <div class="km-item-header">
            <span class="km-item-index">#{{ idx + 1 }}</span>
            <strong class="term">{{ dm.term }}</strong>
            <span class="km-item-table">{{ dm.applicable_table || dm.table }}</span>
            <button type="button" class="km-item-delete" @click="removeDomainMapping(idx)">删除</button>
          </div>
          <div class="km-item-body">
            <pre class="km-item-sql">{{ dm.mapping }}</pre>
          </div>
        </article>
        <div v-if="!knowledge.domain_mappings?.length" class="km-empty">暂无领域映射</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import {
  getKnowledge,
  getKnowledgeStats,
  createExample,
  deleteExample,
  createSynonym,
  deleteSynonym,
  createDomainMapping,
  deleteDomainMapping,
} from '../api'

const props = defineProps({
  embedded: { type: Boolean, default: false },
  datasourceId: { type: String, default: '' },
})
defineEmits(['close'])

function dsId() {
  return props.datasourceId || null
}

const tabs = [
  { key: 'stats', label: '概览' },
  { key: 'examples', label: 'Few-shot 示例' },
  { key: 'synonyms', label: '同义词映射' },
  { key: 'domain', label: '领域映射' },
]

const activeTab = ref('examples')
const knowledge = ref({})
const stats = ref({})

const showExampleForm = ref(false)
const exampleForm = reactive({ question: '', sql: '', tablesStr: '', tagsStr: '' })

const showSynonymForm = ref(false)
const synonymForm = reactive({ synonymsStr: '', target_column: '', table: '' })

const showDomainForm = ref(false)
const domainForm = reactive({ term: '', mapping: '', table: '' })

function tabCount(key) {
  if (key === 'examples') return knowledge.value.question_sql_examples?.length ?? stats.value.examples_count ?? 0
  if (key === 'synonyms') return knowledge.value.synonym_mappings?.length ?? stats.value.synonyms_count ?? 0
  if (key === 'domain') return knowledge.value.domain_mappings?.length ?? stats.value.domain_mappings_count ?? 0
  return null
}

async function loadKnowledge() {
  try {
    const { data } = await getKnowledge(dsId())
    knowledge.value = data
  } catch {
    knowledge.value = {}
  }
  try {
    const { data } = await getKnowledgeStats(dsId())
    stats.value = data
  } catch {
    stats.value = {}
  }
}

async function saveExample() {
  const tables = exampleForm.tablesStr.split(',').map((s) => s.trim()).filter(Boolean)
  const tags = exampleForm.tagsStr.split(',').map((s) => s.trim()).filter(Boolean)
  try {
    await createExample({
      question: exampleForm.question,
      sql: exampleForm.sql,
      tables,
      tags,
      datasource_id: dsId(),
    })
    showExampleForm.value = false
    Object.assign(exampleForm, { question: '', sql: '', tablesStr: '', tagsStr: '' })
    await loadKnowledge()
  } catch (err) {
    alert('保存失败: ' + (err.response?.data?.detail || err.message))
  }
}

async function removeExample(idx) {
  if (!confirm('确认删除此示例？')) return
  try {
    await deleteExample(idx, dsId())
    await loadKnowledge()
  } catch {}
}

async function saveSynonym() {
  const synonyms = synonymForm.synonymsStr.split(',').map((s) => s.trim()).filter(Boolean)
  try {
    await createSynonym({
      synonyms,
      target_column: synonymForm.target_column,
      table: synonymForm.table,
      datasource_id: dsId(),
    })
    showSynonymForm.value = false
    Object.assign(synonymForm, { synonymsStr: '', target_column: '', table: '' })
    await loadKnowledge()
  } catch (err) {
    alert('保存失败: ' + (err.response?.data?.detail || err.message))
  }
}

async function removeSynonym(idx) {
  if (!confirm('确认删除此同义词？')) return
  try {
    await deleteSynonym(idx, dsId())
    await loadKnowledge()
  } catch {}
}

async function saveDomain() {
  try {
    await createDomainMapping({
      term: domainForm.term,
      mapping: domainForm.mapping,
      table: domainForm.table,
      datasource_id: dsId(),
    })
    showDomainForm.value = false
    Object.assign(domainForm, { term: '', mapping: '', table: '' })
    await loadKnowledge()
  } catch (err) {
    alert('保存失败: ' + (err.response?.data?.detail || err.message))
  }
}

async function removeDomainMapping(idx) {
  if (!confirm('确认删除此领域映射？')) return
  try {
    await deleteDomainMapping(idx, dsId())
    await loadKnowledge()
  } catch {}
}

onMounted(loadKnowledge)
</script>

<style scoped>
.knowledge-manager {
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
  background: transparent;
}

/* 抽屉模式（兼容旧调用） */
.knowledge-manager:not(.embedded) {
  position: fixed;
  right: 0;
  top: 0;
  bottom: 0;
  width: min(480px, 100vw);
  background: #fff;
  box-shadow: -12px 0 40px rgba(15, 23, 42, 0.12);
  z-index: 200;
  animation: slideInRight 0.25s ease;
}

/* 独立页面嵌入：铺满父容器 */
.knowledge-manager.embedded {
  position: relative;
  width: 100%;
  max-width: none;
  box-shadow: none;
  animation: none;
  background: transparent;
}

@keyframes slideInRight {
  from { transform: translateX(100%); }
  to { transform: translateX(0); }
}

.km-header.drawer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
  background: #fff;
}

.km-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
}

.km-close-btn {
  background: #f1f5f9;
  border: none;
  color: #64748b;
  cursor: pointer;
  padding: 6px;
  border-radius: 8px;
  display: inline-flex;
}

.km-tabs {
  display: flex;
  gap: 4px;
  padding: 0 4px 0 0;
  border-bottom: 1px solid #e2e8f0;
  background: #fff;
  border-radius: 14px 14px 0 0;
  flex-wrap: wrap;
}

.knowledge-manager.embedded .km-tabs {
  padding: 4px;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  margin-bottom: 14px;
  background: #fff;
}

.km-tab {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 11px 16px;
  background: none;
  border: none;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
  color: #64748b;
  cursor: pointer;
  transition: all 0.15s;
  font-family: inherit;
}

.km-tab:hover {
  color: #0f172a;
  background: #f8fafc;
}

.km-tab.active {
  color: #4338ca;
  background: #eef2ff;
}

.tab-count {
  font-size: 11px;
  font-weight: 700;
  background: #e2e8f0;
  color: #475569;
  padding: 1px 7px;
  border-radius: 999px;
}

.km-tab.active .tab-count {
  background: #c7d2fe;
  color: #3730a3;
}

.km-panel {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 4px 2px 8px;
}

.knowledge-manager:not(.embedded) .km-panel {
  padding: 16px 18px;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 14px;
}

.toolbar h4 {
  margin: 0 0 4px;
  font-size: 15px;
  font-weight: 750;
}

.toolbar p {
  margin: 0;
  font-size: 12px;
  color: #64748b;
}

.km-add-btn {
  padding: 9px 14px;
  background: linear-gradient(135deg, #4f46e5, #6366f1);
  color: #fff;
  border: none;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 650;
  cursor: pointer;
  white-space: nowrap;
  font-family: inherit;
  box-shadow: 0 4px 12px rgba(79, 70, 229, 0.25);
}

.km-add-btn:hover {
  filter: brightness(1.05);
}

.km-form {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 14px;
  margin-bottom: 14px;
  box-shadow: 0 2px 10px rgba(15, 23, 42, 0.03);
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12px;
  font-weight: 650;
  color: #475569;
}

.field.full {
  grid-column: 1 / -1;
}

.km-input,
.km-textarea {
  padding: 9px 11px;
  border: 1.5px solid #e2e8f0;
  border-radius: 10px;
  font-size: 13px;
  background: #fff;
  color: var(--text);
  font-family: inherit;
  outline: none;
}

.km-input:focus,
.km-textarea:focus {
  border-color: #a5b4fc;
  box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
}

.km-textarea {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
  resize: vertical;
  line-height: 1.5;
}

.km-form-actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}

.km-btn-save,
.km-btn-cancel {
  padding: 8px 14px;
  border-radius: 9px;
  font-size: 12px;
  font-weight: 650;
  cursor: pointer;
  font-family: inherit;
  border: none;
}

.km-btn-save {
  background: #4f46e5;
  color: #fff;
}

.km-btn-cancel {
  background: #fff;
  color: #64748b;
  border: 1px solid #e2e8f0;
}

.km-list.cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 12px;
}

.km-item {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 12px 14px;
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.03);
  transition: border-color 0.15s, box-shadow 0.15s;
}

.km-item:hover {
  border-color: #c7d2fe;
  box-shadow: 0 8px 20px rgba(79, 70, 229, 0.08);
}

.km-item-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.km-item-index {
  font-size: 11px;
  color: #94a3b8;
  font-family: ui-monospace, monospace;
  font-weight: 700;
}

.km-item-tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  flex: 1;
}

.km-tag {
  font-size: 10px;
  padding: 2px 7px;
  background: #eef2ff;
  color: #4338ca;
  border-radius: 999px;
  font-weight: 650;
}

.km-item-table {
  font-size: 11px;
  color: #64748b;
  font-family: ui-monospace, monospace;
  background: #f1f5f9;
  padding: 2px 7px;
  border-radius: 6px;
}

.term {
  font-size: 13px;
  color: #0f172a;
}

.km-item-delete {
  margin-left: auto;
  background: none;
  border: none;
  color: #dc2626;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 6px;
  opacity: 0.55;
  transition: opacity 0.15s, background 0.15s;
  font-family: inherit;
}

.km-item:hover .km-item-delete {
  opacity: 1;
}

.km-item-delete:hover {
  background: #fef2f2;
}

.km-item-body {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.km-item-label {
  font-size: 11px;
  color: #94a3b8;
  font-weight: 650;
  margin-top: 4px;
}

.km-item-text {
  font-size: 13px;
  color: #0f172a;
  line-height: 1.5;
}

.km-item-sql {
  background: #0f172a;
  color: #e2e8f0;
  padding: 10px 12px;
  border-radius: 10px;
  font-size: 11px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
  line-height: 1.5;
}

.km-item-meta {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 4px;
}

.km-empty {
  grid-column: 1 / -1;
  text-align: center;
  padding: 48px 20px;
  font-size: 13px;
  color: #94a3b8;
  background: #fff;
  border: 1px dashed #e2e8f0;
  border-radius: 14px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.stat-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 18px 16px;
  text-align: left;
}

.stat-card.accent {
  background: linear-gradient(145deg, #eef2ff, #fff);
  border-color: #c7d2fe;
}

.stat-value {
  font-size: 28px;
  font-weight: 800;
  color: #4f46e5;
  letter-spacing: -0.03em;
  line-height: 1.1;
}

.stat-label {
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
  margin-top: 8px;
}

.stat-hint {
  margin: 4px 0 0;
  font-size: 12px;
  color: #94a3b8;
}

.intro-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 16px 18px;
}

.intro-card h4 {
  margin: 0 0 10px;
  font-size: 14px;
}

.intro-card ul {
  margin: 0;
  padding-left: 18px;
  color: #475569;
  font-size: 13px;
  line-height: 1.75;
}

@media (max-width: 1000px) {
  .stats-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .km-list.cards {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .stats-grid,
  .form-grid {
    grid-template-columns: 1fr;
  }
  .toolbar {
    flex-direction: column;
  }
  .km-add-btn {
    width: 100%;
  }
}
</style>
