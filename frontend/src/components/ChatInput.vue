<template>
  <div class="chat-input-wrapper">
    <div class="input-container">
      <textarea
        ref="textareaRef"
        v-model="inputText"
        class="input-field"
        :placeholder="placeholder"
        :disabled="disabled"
        rows="1"
        @keydown.enter.exact="handleSend"
        @keydown.enter.shift.exact="handleNewLine"
        @input="autoResize"
      ></textarea>
      <div class="input-actions">
        <span class="char-count" v-if="inputText.length > 0">
          {{ inputText.length }}/5000
        </span>
        <button
          v-if="isStreaming"
          class="btn-stop"
          @click="$emit('stop')"
          title="停止生成"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
            <rect x="4" y="4" width="16" height="16" rx="2"/>
          </svg>
        </button>
        <button
          v-else
          class="btn-send"
          :class="{ active: inputText.trim() }"
          :disabled="!inputText.trim() || disabled"
          @click="handleSend"
          title="发送 (Enter)"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
          </svg>
        </button>
      </div>
    </div>
    <div class="input-hint">
      按 Enter 发送，Shift + Enter 换行
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick } from 'vue'

const props = defineProps({
  disabled: { type: Boolean, default: false },
  isStreaming: { type: Boolean, default: false },
})

const emit = defineEmits(['send', 'stop'])

const inputText = ref('')
const textareaRef = ref(null)

const placeholder = computed(() =>
  props.disabled ? '正在生成回答...' : '问点电商数据：比如销售额排名、会员分析、退款率...'
)

function autoResize() {
  nextTick(() => {
    const el = textareaRef.value
    if (el) {
      el.style.height = 'auto'
      el.style.height = Math.min(el.scrollHeight, 150) + 'px'
    }
  })
}

function handleSend(e) {
  e?.preventDefault()
  const text = inputText.value.trim()
  if (!text || props.disabled) return

  emit('send', text)
  inputText.value = ''
  nextTick(autoResize)
}

function handleNewLine() {
  inputText.value += '\n'
  nextTick(autoResize)
}
</script>

<style scoped>
.chat-input-wrapper {
  max-width: 800px;
  margin: 0 auto;
}

.input-container {
  display: flex;
  align-items: flex-end;
  background: var(--bg);
  border: 2px solid var(--border);
  border-radius: var(--radius);
  padding: 10px 14px;
  transition: border-color var(--transition);
}

.input-container:focus-within {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
}

.input-field {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: 14px;
  line-height: 1.6;
  color: var(--text);
  resize: none;
  max-height: 150px;
  font-family: inherit;
}

.input-field::placeholder {
  color: #94a3b8;
}

.input-field:disabled {
  opacity: 0.6;
}

.input-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  padding-left: 8px;
}

.char-count {
  font-size: 11px;
  color: var(--text-secondary);
}

.btn-send {
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 8px;
  background: var(--border);
  color: #94a3b8;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--transition);
}

.btn-send.active {
  background: var(--primary);
  color: #fff;
}

.btn-send.active:hover {
  background: var(--primary-hover);
}

.btn-stop {
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 8px;
  background: var(--danger);
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background var(--transition);
}

.btn-stop:hover {
  background: #dc2626;
}

.input-hint {
  text-align: center;
  font-size: 11px;
  color: #94a3b8;
  margin-top: 6px;
}
</style>