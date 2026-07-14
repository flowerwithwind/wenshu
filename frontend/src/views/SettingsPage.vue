<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h1>系统设置</h1>
        <p>配置大模型供应商、API Key 与默认模型；数据源请前往「数据源」菜单</p>
      </div>
      <button type="button" class="btn primary" @click="showConfig = true">配置模型</button>
    </header>

    <div class="page-body">
      <section class="card current-card">
        <div class="card-head">
          <div>
            <div class="eyebrow">当前使用</div>
            <h2 v-if="status">{{ status.label }} · {{ status.model }}</h2>
            <h2 v-else>加载中…</h2>
            <p v-if="status">{{ status.description || '多供应商可热切换，保存后立即生效' }}</p>
          </div>
          <div v-if="status" class="status-pill" :class="{ ok: status.configured }">
            {{ status.configured ? '已配置 Key' : '未配置 Key' }}
          </div>
        </div>
      </section>

      <section class="card">
        <div class="section-title">
          <h2>可用供应商</h2>
          <span class="muted">点击切换当前供应商（需已配置 API Key）</span>
        </div>

        <div class="provider-grid" v-if="status?.providers?.length">
          <article
            v-for="p in status.providers"
            :key="p.key"
            class="provider-card"
            :class="{ current: p.current, off: !p.available }"
          >
            <div class="provider-top">
              <div class="pname">{{ p.label }}</div>
              <div class="ptags">
                <span v-if="p.current" class="tag on">当前</span>
                <span v-else-if="p.available" class="tag ok">可用</span>
                <span v-else class="tag warn">未配置</span>
              </div>
            </div>
            <div class="pmodel">{{ p.model }}</div>
            <p class="pdesc">{{ p.description }}</p>
            <div class="pactions">
              <button
                v-if="p.available && !p.current"
                type="button"
                class="btn ghost"
                @click="switchTo(p.key)"
              >切换为当前</button>
              <button
                v-else-if="!p.available"
                type="button"
                class="btn ghost"
                @click="showConfig = true"
              >去配置</button>
              <span v-else class="using">正在使用</span>
            </div>
          </article>
        </div>
      </section>

      <section class="card tips">
        <h2>说明</h2>
        <div class="tips-grid">
          <div class="tip">
            <strong>配置存储</strong>
            <p>保存在服务端 <code>data/llm_settings.json</code>，无需手改 .env</p>
          </div>
          <div class="tip">
            <strong>数据源</strong>
            <p>连接管理、SQL 审计请使用左侧「数据源」菜单</p>
          </div>
          <div class="tip">
            <strong>DeepSeek V4</strong>
            <p>推荐模型名 <code>deepseek-v4-flash</code> / <code>deepseek-v4-pro</code></p>
          </div>
        </div>
      </section>
    </div>

    <ModelConfigModal
      v-if="showConfig"
      @close="showConfig = false"
      @saved="onSaved"
    />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { getModels, switchProvider } from '../api'
import ModelConfigModal from '../components/ModelConfigModal.vue'

const status = ref(null)
const showConfig = ref(false)

async function load() {
  try {
    const { data } = await getModels()
    status.value = data
  } catch {
    status.value = null
  }
}

async function switchTo(key) {
  try {
    const { data } = await switchProvider(key)
    status.value = data
  } catch (e) {
    alert(e?.response?.data?.detail || e.message)
    showConfig.value = true
  }
}

function onSaved(data) {
  status.value = data
  showConfig.value = false
}

onMounted(load)
</script>

<style scoped>
.page {
  height: 100%;
  min-height: 0;
  overflow-y: auto;
  padding: 20px 28px 28px;
  box-sizing: border-box;
  background:
    radial-gradient(ellipse 50% 35% at 0% 0%, rgba(79, 70, 229, 0.07), transparent),
    var(--bg);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 18px;
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
  max-width: 640px;
}

.page-body {
  display: flex;
  flex-direction: column;
  gap: 14px;
  width: 100%;
}

.card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  padding: 18px 20px;
  box-shadow: 0 2px 10px rgba(15, 23, 42, 0.03);
}

.current-card {
  background: linear-gradient(120deg, #eef2ff 0%, #fff 55%);
  border-color: #c7d2fe;
}

.card-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.eyebrow {
  font-size: 11px;
  font-weight: 700;
  color: #6366f1;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  margin-bottom: 6px;
}

.card-head h2 {
  margin: 0 0 6px;
  font-size: 20px;
  font-weight: 800;
  letter-spacing: -0.02em;
}

.card-head p {
  margin: 0;
  color: #64748b;
  font-size: 13px;
}

.status-pill {
  flex-shrink: 0;
  font-size: 12px;
  font-weight: 700;
  padding: 6px 10px;
  border-radius: 999px;
  background: #fef3c7;
  color: #b45309;
}

.status-pill.ok {
  background: #d1fae5;
  color: #047857;
}

.section-title {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}

.section-title h2 {
  margin: 0;
  font-size: 15px;
  font-weight: 750;
}

.muted {
  font-size: 12px;
  color: #94a3b8;
}

.provider-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.provider-card {
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 14px;
  background: #f8fafc;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 150px;
}

.provider-card.current {
  border-color: #c7d2fe;
  background: #eef2ff;
}

.provider-card.off {
  opacity: 0.85;
}

.provider-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.pname {
  font-weight: 750;
  font-size: 15px;
}

.pmodel {
  font-size: 12px;
  color: #475569;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 6px 8px;
}

.pdesc {
  margin: 0;
  font-size: 12px;
  color: #64748b;
  line-height: 1.45;
  flex: 1;
}

.pactions {
  margin-top: auto;
}

.using {
  font-size: 12px;
  font-weight: 700;
  color: #4338ca;
}

.tag {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 99px;
}

.tag.on { background: #c7d2fe; color: #3730a3; }
.tag.ok { background: #d1fae5; color: #047857; }
.tag.warn { background: #fef3c7; color: #b45309; }

.tips h2 {
  margin: 0 0 12px;
  font-size: 15px;
}

.tips-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.tip {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 12px 14px;
}

.tip strong {
  display: block;
  font-size: 13px;
  margin-bottom: 6px;
  color: #0f172a;
}

.tip p {
  margin: 0;
  font-size: 12px;
  color: #64748b;
  line-height: 1.55;
}

code {
  background: #e2e8f0;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 11px;
}

.btn {
  border: none;
  border-radius: 10px;
  padding: 8px 14px;
  font-size: 12px;
  font-weight: 650;
  cursor: pointer;
  font-family: inherit;
}

.btn.primary {
  background: linear-gradient(135deg, #4f46e5, #6366f1);
  color: #fff;
  box-shadow: 0 6px 16px rgba(79, 70, 229, 0.28);
  padding: 10px 16px;
  flex-shrink: 0;
}

.btn.ghost {
  background: #fff;
  border: 1px solid #e2e8f0;
  color: #475569;
  width: 100%;
}

.btn.ghost:hover {
  border-color: #c7d2fe;
  color: #4338ca;
  background: #eef2ff;
}

@media (max-width: 1000px) {
  .provider-grid,
  .tips-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .page {
    padding: 16px;
  }
  .page-header {
    flex-direction: column;
    align-items: stretch;
  }
  .btn.primary {
    width: 100%;
  }
}
</style>
