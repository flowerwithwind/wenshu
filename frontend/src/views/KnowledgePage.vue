<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h1>知识库管理</h1>
        <p>Few-shot / 同义词 / 领域映射<strong>按数据源隔离</strong>；切换数据源后编辑的是对应库的知识</p>
      </div>
      <div class="header-actions">
        <label class="ds-pick">
          <span>数据源</span>
          <select v-model="datasourceId">
            <option v-for="ds in datasources" :key="ds.id" :value="ds.id">
              {{ ds.name }}{{ ds.is_default ? '（默认）' : '' }}
            </option>
          </select>
        </label>
        <button type="button" class="btn ghost" :disabled="!datasourceId || busy" @click="runBootstrap(false)">
          {{ busy && !useLlmBusy ? '扫描中…' : '扫描 Schema 生成' }}
        </button>
        <button type="button" class="btn primary" :disabled="!datasourceId || busy" @click="runBootstrap(true)">
          {{ useLlmBusy ? 'AI 增强中…' : 'AI 增强知识库' }}
        </button>
      </div>
    </header>
    <p v-if="tip" class="tip" :class="{ err: tipErr }">{{ tip }}</p>
    <div class="content">
      <KnowledgeManager :key="datasourceId + '-' + refreshKey" embedded :datasource-id="datasourceId" />
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import KnowledgeManager from '../components/KnowledgeManager.vue'
import { listDatasources, bootstrapKnowledge } from '../api'

const datasources = ref([])
const datasourceId = ref('')
const refreshKey = ref(0)
const busy = ref(false)
const useLlmBusy = ref(false)
const tip = ref('')
const tipErr = ref(false)

async function runBootstrap(useLlm) {
  if (!datasourceId.value) return
  busy.value = true
  useLlmBusy.value = !!useLlm
  tip.value = ''
  tipErr.value = false
  try {
    const { data } = await bootstrapKnowledge(datasourceId.value, { useLlm, merge: true })
    tip.value = data.message || '知识库已更新'
    refreshKey.value += 1
  } catch (e) {
    tipErr.value = true
    tip.value = e?.response?.data?.detail || e.message || '操作失败'
  } finally {
    busy.value = false
    useLlmBusy.value = false
  }
}

onMounted(async () => {
  try {
    const { data } = await listDatasources()
    datasources.value = data.items || []
    const def = datasources.value.find((d) => d.is_default) || datasources.value[0]
    datasourceId.value = def?.id || ''
  } catch {
    datasources.value = []
  }
})
</script>

<style scoped>
.page {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-sizing: border-box;
  padding: 20px 28px 20px;
  background:
    radial-gradient(ellipse 60% 40% at 100% 0%, rgba(79, 70, 229, 0.06), transparent),
    var(--bg);
}

.page-header {
  flex-shrink: 0;
  margin-bottom: 14px;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  flex-wrap: wrap;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.ds-pick {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 650;
  color: #64748b;
}
.ds-pick select {
  border: none;
  outline: none;
  font-size: 13px;
  font-weight: 650;
  color: #0f172a;
  min-width: 180px;
  font-family: inherit;
  background: transparent;
}
.btn {
  border: none;
  border-radius: 10px;
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 650;
  cursor: pointer;
  font-family: inherit;
}
.btn:disabled { opacity: 0.55; cursor: not-allowed; }
.btn.ghost {
  background: #fff;
  border: 1px solid #e2e8f0;
  color: #475569;
}
.btn.primary {
  background: linear-gradient(135deg, #4f46e5, #6366f1);
  color: #fff;
}
.tip {
  margin: 0 0 12px;
  padding: 10px 12px;
  border-radius: 10px;
  font-size: 13px;
  background: #eef2ff;
  color: #3730a3;
  border: 1px solid #c7d2fe;
}
.tip.err {
  background: #fef2f2;
  color: #b91c1c;
  border-color: #fecaca;
}

.page-header h1 {
  margin: 0 0 6px;
  font-size: 22px;
  font-weight: 800;
  letter-spacing: -0.02em;
}

.page-header p {
  margin: 0;
  color: #64748b;
  font-size: 13px;
  line-height: 1.5;
  max-width: 720px;
}

.content {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

@media (max-width: 640px) {
  .page {
    padding: 16px;
  }
}
</style>
