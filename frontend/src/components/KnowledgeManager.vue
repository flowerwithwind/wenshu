<template>
  <div class="knowledge-manager">
    <div class="km-header">
      <h3>知识库管理</h3>
      <button class="km-close-btn" @click="$emit('close')">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </button>
    </div>

    <!-- 标签页切换 -->
    <div class="km-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="km-tab"
        :class="{ active: activeTab === tab.key }"
        @click="activeTab = tab.key"
      >{{ tab.label }}</button>
    </div>

    <!-- 统计 -->
    <div v-if="activeTab === 'stats'" class="km-panel">
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-value">{{ stats.examples_count || 0 }}</div>
          <div class="stat-label">Few-shot 示例</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ stats.synonyms_count || 0 }}</div>
          <div class="stat-label">同义词映射</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ stats.domain_mappings_count || 0 }}</div>
          <div class="stat-label">领域映射</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ stats.table_schemas_count || 0 }}</div>
          <div class="stat-label">表 Schema</div>
        </div>
      </div>
    </div>

    <!-- Few-shot 示例 -->
    <div v-if="activeTab === 'examples'" class="km-panel">
      <button class="km-add-btn" @click="showExampleForm = true">+ 新增示例</button>
      <div v-if="showExampleForm" class="km-form">
        <input v-model="exampleForm.question" placeholder="问题" class="km-input" />
        <textarea v-model="exampleForm.sql" placeholder="SQL" class="km-textarea" rows="3"></textarea>
        <input v-model="exampleForm.tablesStr" placeholder="关联表（逗号分隔）" class="km-input" />
        <input v-model="exampleForm.tagsStr" placeholder="标签（逗号分隔）" class="km-input" />
        <div class="km-form-actions">
          <button class="km-btn-save" @click="saveExample">保存</button>
          <button class="km-btn-cancel" @click="showExampleForm = false">取消</button>
        </div>
      </div>
      <div class="km-list">
        <div v-for="(ex, idx) in knowledge.question_sql_examples" :key="idx" class="km-item">
          <div class="km-item-header">
            <span class="km-item-index">#{{ idx }}</span>
            <span class="km-item-tags">
              <span v-for="tag in ex.tags" :key="tag" class="km-tag">{{ tag }}</span>
            </span>
            <button class="km-item-delete" @click="removeExample(idx)">删除</button>
          </div>
          <div class="km-item-body">
            <div class="km-item-label">问题</div>
            <div class="km-item-text">{{ ex.question }}</div>
            <div class="km-item-label">SQL</div>
            <pre class="km-item-sql">{{ ex.sql }}</pre>
          </div>
        </div>
        <div v-if="!knowledge.question_sql_examples?.length" class="km-empty">暂无示例</div>
      </div>
    </div>

    <!-- 同义词映射 -->
    <div v-if="activeTab === 'synonyms'" class="km-panel">
      <button class="km-add-btn" @click="showSynonymForm = true">+ 新增同义词</button>
      <div v-if="showSynonymForm" class="km-form">
        <input v-model="synonymForm.synonymsStr" placeholder="同义词（逗号分隔）" class="km-input" />
        <input v-model="synonymForm.target_column" placeholder="目标列名" class="km-input" />
        <input v-model="synonymForm.table" placeholder="所属表" class="km-input" />
        <div class="km-form-actions">
          <button class="km-btn-save" @click="saveSynonym">保存</button>
          <button class="km-btn-cancel" @click="showSynonymForm = false">取消</button>
        </div>
      </div>
      <div class="km-list">
        <div v-for="(syn, idx) in knowledge.synonym_mappings" :key="idx" class="km-item">
          <div class="km-item-header">
            <span class="km-item-index">#{{ idx }}</span>
            <span class="km-item-table">{{ syn.table }}.{{ syn.target_column }}</span>
            <button class="km-item-delete" @click="removeSynonym(idx)">删除</button>
          </div>
          <div class="km-item-body">
            <div class="km-item-tags">
              <span v-for="s in syn.synonyms" :key="s" class="km-tag">{{ s }}</span>
            </div>
          </div>
        </div>
        <div v-if="!knowledge.synonym_mappings?.length" class="km-empty">暂无同义词映射</div>
      </div>
    </div>

    <!-- 领域映射 -->
    <div v-if="activeTab === 'domain'" class="km-panel">
      <button class="km-add-btn" @click="showDomainForm = true">+ 新增领域映射</button>
      <div v-if="showDomainForm" class="km-form">
        <input v-model="domainForm.term" placeholder="术语" class="km-input" />
        <input v-model="domainForm.mapping" placeholder="SQL映射" class="km-input" />
        <input v-model="domainForm.table" placeholder="适用表" class="km-input" />
        <div class="km-form-actions">
          <button class="km-btn-save" @click="saveDomain">保存</button>
          <button class="km-btn-cancel" @click="showDomainForm = false">取消</button>
        </div>
      </div>
      <div class="km-list">
        <div v-for="(dm, idx) in knowledge.domain_mappings" :key="idx" class="km-item">
          <div class="km-item-header">
            <span class="km-item-index">#{{ idx }}</span>
            <strong>{{ dm.term }}</strong>
            <span class="km-item-table">{{ dm.applicable_table }}</span>
            <button class="km-item-delete" @click="removeDomainMapping(idx)">删除</button>
          </div>
          <div class="km-item-body">
            <pre class="km-item-sql">{{ dm.mapping }}</pre>
          </div>
        </div>
        <div v-if="!knowledge.domain_mappings?.length" class="km-empty">暂无领域映射</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getKnowledge, getKnowledgeStats, createExample, deleteExample, createSynonym, deleteSynonym, createDomainMapping, deleteDomainMapping } from '../api'

const emit = defineEmits(['close'])

const tabs = [
  { key: 'stats', label: '统计' },
  { key: 'examples', label: 'Few-shot 示例' },
  { key: 'synonyms', label: '同义词映射' },
  { key: 'domain', label: '领域映射' },
]

const activeTab = ref('stats')
const knowledge = ref({})
const stats = ref({})

const showExampleForm = ref(false)
const exampleForm = reactive({ question: '', sql: '', tablesStr: '', tagsStr: '' })

const showSynonymForm = ref(false)
const synonymForm = reactive({ synonymsStr: '', target_column: '', table: '' })

const showDomainForm = ref(false)
const domainForm = reactive({ term: '', mapping: '', table: '' })

async function loadKnowledge() {
  try {
    const { data } = await getKnowledge()
    knowledge.value = data
  } catch {}
  try {
    const { data } = await getKnowledgeStats()
    stats.value = data
  } catch {}
}

async function saveExample() {
  const tables = exampleForm.tablesStr.split(',').map(s => s.trim()).filter(Boolean)
  const tags = exampleForm.tagsStr.split(',').map(s => s.trim()).filter(Boolean)
  try {
    await createExample({
      question: exampleForm.question,
      sql: exampleForm.sql,
      tables,
      tags,
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
    await deleteExample(idx)
    await loadKnowledge()
  } catch {}
}

async function saveSynonym() {
  const synonyms = synonymForm.synonymsStr.split(',').map(s => s.trim()).filter(Boolean)
  try {
    await createSynonym({
      synonyms,
      target_column: synonymForm.target_column,
      table: synonymForm.table,
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
    await deleteSynonym(idx)
    await loadKnowledge()
  } catch {}
}

async function saveDomain() {
  try {
    await createDomainMapping({
      term: domainForm.term,
      mapping: domainForm.mapping,
      table: domainForm.table,
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
    await deleteDomainMapping(idx)
    await loadKnowledge()
  } catch {}
}

onMounted(() => {
  loadKnowledge()
})
</script>

<style scoped>
.knowledge-manager {
  position: fixed;
  right: 0;
  top: 0;
  bottom: 0;
  width: 440px;
  max-width: 90vw;
  background: var(--bg-card);
  box-shadow: var(--shadow-lg);
  z-index: 200;
  display: flex;
  flex-direction: column;
  animation: slideInRight 0.3s ease;
}

@keyframes slideInRight {
  from { transform: translateX(100%); }
  to { transform: translateX(0); }
}

.km-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
}

.km-header h3 {
  font-size: 16px;
  font-weight: 600;
}

.km-close-btn {
  background: none;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
}

.km-close-btn:hover {
  background: var(--bg);
  color: var(--text);
}

.km-tabs {
  display: flex;
  border-bottom: 1px solid var(--border);
  padding: 0 20px;
}

.km-tab {
  padding: 10px 16px;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  font-size: 13px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--transition);
}

.km-tab.active {
  color: var(--primary);
  border-bottom-color: var(--primary);
}

.km-tab:hover {
  color: var(--text);
}

.km-panel {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
}

.km-add-btn {
  padding: 8px 16px;
  background: var(--primary);
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  margin-bottom: 12px;
  transition: background var(--transition);
}

.km-add-btn:hover {
  background: var(--primary-hover);
}

.km-form {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 12px;
  margin-bottom: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.km-input {
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 13px;
  background: var(--bg-card);
  color: var(--text);
}

.km-textarea {
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 12px;
  font-family: 'SF Mono', 'Fira Code', monospace;
  background: var(--bg-card);
  color: var(--text);
  resize: vertical;
}

.km-form-actions {
  display: flex;
  gap: 8px;
}

.km-btn-save {
  padding: 6px 14px;
  background: var(--primary);
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
}

.km-btn-cancel {
  padding: 6px 14px;
  background: var(--bg-card);
  color: var(--text-secondary);
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
}

.km-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.km-item {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 10px 12px;
}

.km-item-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.km-item-index {
  font-size: 11px;
  color: var(--text-secondary);
  font-family: monospace;
}

.km-item-tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  flex: 1;
}

.km-tag {
  font-size: 10px;
  padding: 2px 6px;
  background: var(--primary-light);
  color: var(--primary);
  border-radius: 10px;
  font-weight: 500;
}

.km-item-table {
  font-size: 11px;
  color: var(--text-secondary);
  font-family: monospace;
}

.km-item-delete {
  background: none;
  border: none;
  color: var(--danger);
  font-size: 12px;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
  opacity: 0;
  transition: opacity 0.15s;
}

.km-item:hover .km-item-delete {
  opacity: 1;
}

.km-item-delete:hover {
  background: rgba(239, 68, 68, 0.1);
}

.km-item-body {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.km-item-label {
  font-size: 11px;
  color: var(--text-secondary);
  font-weight: 500;
}

.km-item-text {
  font-size: 13px;
  color: var(--text);
  line-height: 1.5;
}

.km-item-sql {
  background: #1e293b;
  color: #e2e8f0;
  padding: 8px 10px;
  border-radius: 6px;
  font-size: 11px;
  font-family: 'SF Mono', 'Fira Code', monospace;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

.km-empty {
  text-align: center;
  padding: 24px;
  font-size: 13px;
  color: var(--text-secondary);
}

.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.stat-card {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 16px;
  text-align: center;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--primary);
}

.stat-label {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 4px;
}
</style>