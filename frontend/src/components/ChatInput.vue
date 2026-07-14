<template>
  <div class="chat-input-wrapper">
    <div class="input-container" :class="{ disabled, streaming: isStreaming }">
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
          type="button"
          @click="$emit('stop')"
          title="停止生成"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
            <rect x="5" y="5" width="14" height="14" rx="2"/>
          </svg>
        </button>
        <button
          v-else
          class="btn-send"
          type="button"
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
      Enter 发送 · Shift+Enter 换行
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
  props.isStreaming
    ? '模型正在思考，请稍候…'
    : props.disabled
      ? '请稍候…'
      : '问点电商数据：销售额排名、会员分析、退款率…'
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
  if (!text || props.disabled || props.isStreaming) return

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
  max-width: 820px;
  margin: 0 auto;
}

.input-container {
  display: flex;
  align-items: center; /* 单行时垂直居中，避免上下边距不均 */
  gap: 10px;
  background: #fff;
  border: 1.5px solid var(--border);
  border-radius: 16px;
  padding: 10px 12px 10px 16px; /* 上下一致 */
  min-height: 52px;
  box-shadow: 0 2px 12px rgba(15, 23, 42, 0.04);
  transition: border-color 0.15s, box-shadow 0.15s;
}

.input-container:focus-within {
  border-color: #a5b4fc;
  box-shadow: 0 0 0 4px rgba(79, 70, 229, 0.1), 0 4px 16px rgba(79, 70, 229, 0.06);
}

.input-container.streaming {
  border-color: #c7d2fe;
  background: linear-gradient(180deg, #fff, #f8fafc);
}

.input-container.disabled {
  opacity: 0.85;
}

.input-field {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: 14px;
  line-height: 22px; /* 固定行高，与 padding 对称 */
  color: var(--text);
  resize: none;
  max-height: 150px;
  min-height: 22px;
  padding: 0; /* 容器已承担上下内边距，textarea 自身不再额外加 */
  margin: 0;
  font-family: inherit;
  vertical-align: middle;
}

.input-field::placeholder {
  color: #94a3b8;
  line-height: 22px;
}

.input-field:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.input-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  align-self: flex-end; /* 多行时按钮贴底 */
  padding-bottom: 0;
}

.char-count {
  font-size: 11px;
  color: var(--text-secondary);
  line-height: 1;
}

.btn-send,
.btn-stop {
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 10px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
  flex-shrink: 0;
}

.btn-send {
  background: #e2e8f0;
  color: #94a3b8;
}

.btn-send.active {
  background: linear-gradient(135deg, #4f46e5, #6366f1);
  color: #fff;
  box-shadow: 0 4px 12px rgba(79, 70, 229, 0.35);
}

.btn-send.active:hover {
  filter: brightness(1.05);
  transform: translateY(-1px);
}

.btn-send:disabled {
  cursor: not-allowed;
}

.btn-stop {
  background: #fee2e2;
  color: #dc2626;
}

.btn-stop:hover {
  background: #fecaca;
}

.input-hint {
  text-align: center;
  font-size: 11px;
  color: #94a3b8;
  margin-top: 8px;
  letter-spacing: 0.02em;
}
</style>
