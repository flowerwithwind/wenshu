<template>
  <Teleport to="body">
    <div class="toast-container">
      <TransitionGroup name="toast">
        <div
          v-for="item in toasts"
          :key="item.id"
          class="toast-item"
          :class="item.type"
        >
          <span class="toast-text">{{ item.message }}</span>
          <button class="toast-close" @click="remove(item.id)">×</button>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<script setup>
import { ref } from 'vue'

const toasts = ref([])
let counter = 0

function add(message, type = 'info', duration = 4000) {
  const id = ++counter
  toasts.value.push({ id, message, type })
  if (duration > 0) {
    setTimeout(() => remove(id), duration)
  }
  return id
}

function remove(id) {
  const idx = toasts.value.findIndex((t) => t.id === id)
  if (idx !== -1) toasts.value.splice(idx, 1)
}

/** 快捷方法 */
function success(msg) { add(msg, 'success') }
function error(msg) { add(msg, 'error', 6000) }
function info(msg) { add(msg, 'info') }

// 暴露到父组件
defineExpose({ add, success, error, info })
</script>

<style scoped>
.toast-container {
  position: fixed;
  top: 20px;
  right: 20px;
  z-index: 10000;
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: 400px;
  pointer-events: none;
}

.toast-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border-radius: 12px;
  font-size: 13px;
  font-weight: 500;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
  pointer-events: auto;
  animation: toastIn 0.25s ease;
}

.toast-item.success {
  background: #ecfdf5;
  color: #065f46;
  border: 1px solid #a7f3d0;
}

.toast-item.error {
  background: #fef2f2;
  color: #991b1b;
  border: 1px solid #fecaca;
}

.toast-item.info {
  background: #eff6ff;
  color: #1e40af;
  border: 1px solid #bfdbfe;
}

.toast-text {
  flex: 1;
  line-height: 1.4;
}

.toast-close {
  border: none;
  background: none;
  color: inherit;
  opacity: 0.5;
  cursor: pointer;
  font-size: 16px;
  padding: 0 2px;
  line-height: 1;
}

.toast-close:hover {
  opacity: 1;
}

/* 过渡动画 */
.toast-enter-active { animation: toastIn 0.25s ease; }
.toast-leave-active { animation: toastOut 0.2s ease; }

@keyframes toastIn {
  from { opacity: 0; transform: translateX(20px); }
  to { opacity: 1; transform: translateX(0); }
}

@keyframes toastOut {
  from { opacity: 1; transform: translateX(0); }
  to { opacity: 0; transform: translateX(20px); }
}
</style>
