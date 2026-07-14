<template>
  <div class="modal-mask" @click.self="$emit('close')">
    <div class="modal-panel">
      <header class="modal-header">
        <div>
          <h3>模型配置</h3>
          <p>在此填写 API Key 与模型名称，无需修改 .env 文件</p>
        </div>
        <button class="btn-close" type="button" @click="$emit('close')">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </header>

      <div class="modal-body" v-if="!loading">
        <label class="field">
          <span class="field-label">当前使用</span>
          <select v-model="form.provider" class="field-input">
            <option v-for="p in providerOptions" :key="p.key" :value="p.key">
              {{ p.label }}{{ p.has_key ? '' : '（未配置 Key）' }}
            </option>
          </select>
        </label>

        <div class="provider-tabs">
          <button
            v-for="p in providerOptions"
            :key="p.key"
            type="button"
            class="tab"
            :class="{ active: activeTab === p.key }"
            @click="activeTab = p.key"
          >{{ p.label }}</button>
        </div>

        <div v-for="p in providerOptions" :key="p.key + '-form'" v-show="activeTab === p.key" class="provider-form">
          <label class="field">
            <span class="field-label">API Key</span>
            <div class="key-row">
              <input
                v-model="form[p.key].api_key"
                class="field-input"
                :type="showKey[p.key] ? 'text' : 'password'"
                :placeholder="form[p.key].has_key ? form[p.key].api_key_masked || '已配置，留空不修改' : 'sk-...'"
                autocomplete="off"
              />
              <button type="button" class="btn-eye" @click="showKey[p.key] = !showKey[p.key]">
                {{ showKey[p.key] ? '隐藏' : '显示' }}
              </button>
            </div>
            <span class="field-hint" v-if="form[p.key].has_key">已保存 Key：{{ form[p.key].api_key_masked }}，填写新值可覆盖</span>
          </label>

          <label class="field" v-if="p.key !== 'anthropic'">
            <span class="field-label">Base URL</span>
            <input v-model="form[p.key].base_url" class="field-input" placeholder="https://..." />
          </label>

          <label class="field">
            <span class="field-label">模型名称</span>
            <input v-model="form[p.key].model" class="field-input" :placeholder="p.defaultModel" />
          </label>
        </div>

        <p class="error" v-if="error">{{ error }}</p>
        <p class="success" v-if="success">{{ success }}</p>
      </div>
      <div v-else class="modal-loading">加载配置中…</div>

      <footer class="modal-footer">
        <button type="button" class="btn ghost" @click="$emit('close')">取消</button>
        <button type="button" class="btn primary" :disabled="saving" @click="save">
          {{ saving ? '保存中…' : '保存并应用' }}
        </button>
      </footer>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted, computed } from 'vue'
import { getModels, saveModelConfig } from '../api'

const emit = defineEmits(['close', 'saved'])

const loading = ref(true)
const saving = ref(false)
const error = ref('')
const success = ref('')
const activeTab = ref('deepseek')
const showKey = reactive({ deepseek: false, openai: false, anthropic: false })

const form = reactive({
  provider: 'deepseek',
  deepseek: { api_key: '', base_url: '', model: '', has_key: false, api_key_masked: '' },
  openai: { api_key: '', base_url: '', model: '', has_key: false, api_key_masked: '' },
  anthropic: { api_key: '', base_url: '', model: '', has_key: false, api_key_masked: '' },
})

const providerOptions = computed(() => [
  { key: 'deepseek', label: 'DeepSeek', has_key: form.deepseek.has_key, defaultModel: 'deepseek-chat' },
  { key: 'openai', label: 'OpenAI', has_key: form.openai.has_key, defaultModel: 'gpt-4o' },
  { key: 'anthropic', label: 'Anthropic', has_key: form.anthropic.has_key, defaultModel: 'claude-sonnet-4-20250514' },
])

async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await getModels()
    form.provider = data.provider || 'deepseek'
    activeTab.value = form.provider
    const s = data.settings || {}
    for (const name of ['deepseek', 'openai', 'anthropic']) {
      const block = s[name] || {}
      form[name].api_key = ''
      form[name].base_url = block.base_url || ''
      form[name].model = block.model || ''
      form[name].has_key = !!block.has_key
      form[name].api_key_masked = block.api_key_masked || ''
    }
  } catch (e) {
    error.value = e?.response?.data?.detail || e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  error.value = ''
  success.value = ''
  try {
    const payload = {
      provider: form.provider,
      deepseek: {
        api_key: form.deepseek.api_key || undefined,
        base_url: form.deepseek.base_url || undefined,
        model: form.deepseek.model || undefined,
      },
      openai: {
        api_key: form.openai.api_key || undefined,
        base_url: form.openai.base_url || undefined,
        model: form.openai.model || undefined,
      },
      anthropic: {
        api_key: form.anthropic.api_key || undefined,
        model: form.anthropic.model || undefined,
      },
    }
    const { data } = await saveModelConfig(payload)
    success.value = `已保存，当前使用 ${data.label} / ${data.model}`
    emit('saved', data)
    // 刷新表单掩码状态
    await load()
    success.value = `已保存，当前使用 ${data.label} / ${data.model}`
  } catch (e) {
    error.value = e?.response?.data?.detail || e.message || '保存失败'
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  backdrop-filter: blur(4px);
  z-index: 200;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  animation: fade 0.15s ease;
}

.modal-panel {
  width: min(520px, 100%);
  max-height: min(90vh, 720px);
  background: #fff;
  border-radius: 18px;
  box-shadow: 0 24px 64px rgba(15, 23, 42, 0.2);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.modal-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 18px 20px 12px;
  border-bottom: 1px solid #f1f5f9;
}

.modal-header h3 {
  font-size: 17px;
  font-weight: 750;
  color: #0f172a;
  margin: 0 0 4px;
}

.modal-header p {
  margin: 0;
  font-size: 12px;
  color: #94a3b8;
}

.btn-close {
  border: none;
  background: #f8fafc;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  cursor: pointer;
  color: #64748b;
  display: flex;
  align-items: center;
  justify-content: center;
}

.btn-close:hover {
  background: #f1f5f9;
  color: #0f172a;
}

.modal-body {
  padding: 16px 20px;
  overflow-y: auto;
  flex: 1;
}

.modal-loading {
  padding: 40px;
  text-align: center;
  color: #94a3b8;
  font-size: 13px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 14px;
}

.field-label {
  font-size: 12px;
  font-weight: 600;
  color: #475569;
}

.field-input {
  border: 1.5px solid #e2e8f0;
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 13px;
  font-family: inherit;
  outline: none;
  transition: border-color 0.15s, box-shadow 0.15s;
  background: #fff;
}

.field-input:focus {
  border-color: #a5b4fc;
  box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
}

.field-hint {
  font-size: 11px;
  color: #94a3b8;
}

.key-row {
  display: flex;
  gap: 8px;
}

.key-row .field-input {
  flex: 1;
}

.btn-eye {
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  border-radius: 10px;
  padding: 0 12px;
  font-size: 12px;
  color: #64748b;
  cursor: pointer;
  white-space: nowrap;
}

.provider-tabs {
  display: flex;
  gap: 6px;
  margin: 8px 0 14px;
  background: #f1f5f9;
  padding: 4px;
  border-radius: 12px;
}

.tab {
  flex: 1;
  border: none;
  background: transparent;
  padding: 8px;
  border-radius: 9px;
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  cursor: pointer;
}

.tab.active {
  background: #fff;
  color: #4f46e5;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}

.provider-form {
  animation: fade 0.15s ease;
}

.error {
  color: #dc2626;
  font-size: 12px;
  background: #fef2f2;
  padding: 8px 10px;
  border-radius: 8px;
}

.success {
  color: #059669;
  font-size: 12px;
  background: #ecfdf5;
  padding: 8px 10px;
  border-radius: 8px;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 14px 20px;
  border-top: 1px solid #f1f5f9;
  background: #fafbfc;
}

.btn {
  border: none;
  border-radius: 10px;
  padding: 10px 16px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  font-family: inherit;
}

.btn.ghost {
  background: #fff;
  border: 1px solid #e2e8f0;
  color: #64748b;
}

.btn.primary {
  background: linear-gradient(135deg, #4f46e5, #6366f1);
  color: #fff;
  box-shadow: 0 4px 12px rgba(79, 70, 229, 0.3);
}

.btn.primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

@keyframes fade {
  from { opacity: 0; }
  to { opacity: 1; }
}
</style>
