<template>
  <div class="feedback-bar">
    <button
      class="feedback-btn"
      :class="{ active: rating === 'like' }"
      @click="rate('like')"
      title="有帮助"
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3H14z"/>
        <path d="M7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/>
      </svg>
      有帮助
    </button>
    <button
      class="feedback-btn"
      :class="{ active: rating === 'dislike' }"
      @click="rate('dislike')"
      title="不准确"
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3H10z"/>
        <path d="M17 2h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/>
      </svg>
      不准确
    </button>
    <span v-if="submitted" class="feedback-thanks">感谢反馈！</span>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import api from '../api'

const props = defineProps({
  messageId: { type: String, required: true },
})

const rating = ref(null)
const submitted = ref(false)

async function rate(val) {
  if (submitted.value) return
  rating.value = val
  try {
    await api.post('/feedback', {
      message_id: props.messageId,
      rating: val,
    })
    submitted.value = true
  } catch (e) {
    console.error('Feedback submit failed:', e)
  }
}
</script>

<style scoped>
.feedback-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  padding-top: 8px;
  border-top: 1px solid #f1f5f9;
}

.feedback-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--transition);
}

.feedback-btn:hover {
  border-color: var(--primary);
  color: var(--primary);
}

.feedback-btn.active {
  background: var(--primary-light);
  border-color: var(--primary);
  color: var(--primary);
}

.feedback-thanks {
  font-size: 12px;
  color: var(--success);
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
</style>