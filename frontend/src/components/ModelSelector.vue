<template>
  <div class="model-selector" ref="rootRef">
    <button
      class="model-trigger"
      type="button"
      :disabled="disabled || loading"
      @click="open = !open"
      title="当前模型"
    >
      <span class="model-dot" :class="{ ok: current?.configured }"></span>
      <span class="model-text">
        <span class="model-label">{{ current?.label || 'DeepSeek' }}</span>
        <span class="model-name">{{ current?.model || 'deepseek-chat' }}</span>
      </span>
      <svg class="chevron" :class="{ open }" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polyline points="6 9 12 15 18 9"/>
      </svg>
    </button>

    <div v-if="open" class="model-dropdown">
      <div class="dropdown-title">快速切换</div>
      <button
        v-for="p in providers"
        :key="p.key"
        type="button"
        class="provider-item"
        :class="{ active: p.current, disabled: !p.available }"
        :disabled="!p.available || switching"
        @click="select(p)"
      >
        <div class="provider-main">
          <span class="provider-label">{{ p.label }}</span>
          <span class="provider-model">{{ p.model }}</span>
        </div>
        <div class="provider-meta">
          <span v-if="p.current" class="tag current">当前</span>
          <span v-else-if="!p.available" class="tag missing">未配置</span>
          <span v-else class="tag ok">可用</span>
        </div>
      </button>

      <button type="button" class="btn-config" @click="openConfig">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="3"/>
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
        </svg>
        配置 API Key / 模型
      </button>
    </div>

    <ModelConfigModal
      v-if="showConfig"
      @close="showConfig = false"
      @saved="onConfigSaved"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { getModels, switchProvider } from '../api'
import ModelConfigModal from './ModelConfigModal.vue'

const props = defineProps({
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(['changed'])

const open = ref(false)
const showConfig = ref(false)
const loading = ref(false)
const switching = ref(false)
const status = ref(null)
const rootRef = ref(null)

const providers = computed(() => status.value?.providers || [])
const current = computed(() => {
  if (!status.value) {
    return { label: 'DeepSeek', model: 'deepseek-chat', configured: false }
  }
  return {
    label: status.value.label,
    model: status.value.model,
    configured: status.value.configured,
  }
})

async function load() {
  loading.value = true
  try {
    const { data } = await getModels()
    status.value = data
    emit('changed', data)
  } catch {
    status.value = {
      provider: 'deepseek',
      label: 'DeepSeek',
      model: 'deepseek-chat',
      configured: false,
      providers: [],
    }
  } finally {
    loading.value = false
  }
}

async function select(p) {
  if (!p.available || p.current || switching.value) {
    if (!p.available) {
      open.value = false
      showConfig.value = true
    }
    return
  }
  switching.value = true
  try {
    const { data } = await switchProvider(p.key)
    status.value = data
    open.value = false
    emit('changed', data)
  } catch (e) {
    const msg = e?.response?.data?.detail || e.message || '切换失败'
    alert(msg)
    if (String(msg).includes('Key') || String(msg).includes('配置')) {
      showConfig.value = true
    }
  } finally {
    switching.value = false
  }
}

function openConfig() {
  open.value = false
  showConfig.value = true
}

function onConfigSaved(data) {
  status.value = data
  showConfig.value = false
  emit('changed', data)
}

function onDocClick(e) {
  if (showConfig.value) return
  if (rootRef.value && !rootRef.value.contains(e.target)) {
    open.value = false
  }
}

onMounted(() => {
  load()
  document.addEventListener('click', onDocClick)
})

onUnmounted(() => {
  document.removeEventListener('click', onDocClick)
})

defineExpose({ reload: load, openConfig })
</script>

<style scoped>
.model-selector {
  position: relative;
}

.model-trigger {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 5px 10px 5px 8px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: linear-gradient(180deg, #fff, #f8fafc);
  cursor: pointer;
  transition: all 0.15s;
  max-width: 220px;
}

.model-trigger:hover:not(:disabled) {
  border-color: #c7d2fe;
  box-shadow: 0 2px 8px rgba(79, 70, 229, 0.08);
}

.model-trigger:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.model-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #fbbf24;
  flex-shrink: 0;
}

.model-dot.ok {
  background: #10b981;
  box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.15);
}

.model-text {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  min-width: 0;
  line-height: 1.2;
}

.model-label {
  font-size: 12px;
  font-weight: 700;
  color: #334155;
}

.model-name {
  font-size: 10px;
  color: #94a3b8;
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chevron {
  color: #94a3b8;
  transition: transform 0.15s;
  flex-shrink: 0;
}

.chevron.open {
  transform: rotate(180deg);
}

.model-dropdown {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  width: 280px;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 14px;
  box-shadow: 0 12px 40px rgba(15, 23, 42, 0.12);
  padding: 10px;
  z-index: 50;
  animation: dropIn 0.15s ease;
}

.dropdown-title {
  font-size: 11px;
  font-weight: 600;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding: 4px 8px 8px;
}

.provider-item {
  width: 100%;
  text-align: left;
  border: 1px solid transparent;
  background: transparent;
  border-radius: 10px;
  padding: 10px;
  cursor: pointer;
  transition: all 0.15s;
  margin-bottom: 4px;
}

.provider-item:hover:not(:disabled) {
  background: #f8fafc;
  border-color: #e2e8f0;
}

.provider-item.active {
  background: #eef2ff;
  border-color: #c7d2fe;
}

.provider-item.disabled {
  opacity: 0.7;
  cursor: pointer;
}

.provider-main {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.provider-label {
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
}

.provider-model {
  font-size: 11px;
  color: #64748b;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}

.provider-meta {
  margin-top: 4px;
}

.tag {
  font-size: 10px;
  padding: 1px 7px;
  border-radius: 99px;
  font-weight: 600;
}

.tag.current { background: #e0e7ff; color: #4338ca; }
.tag.ok { background: #ecfdf5; color: #059669; }
.tag.missing { background: #fef3c7; color: #d97706; }

.btn-config {
  width: 100%;
  margin-top: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px;
  border: 1px dashed #c7d2fe;
  border-radius: 10px;
  background: #eef2ff;
  color: #4338ca;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}

.btn-config:hover {
  background: #e0e7ff;
  border-style: solid;
}

@keyframes dropIn {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
