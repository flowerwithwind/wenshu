<template>
  <div class="source-citation">
    <button class="citation-toggle" @click="expanded = !expanded">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
        <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
      </svg>
      数据来源 ({{ sources.length }})
      <svg
        class="chevron"
        :class="{ rotated: expanded }"
        width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
      >
        <polyline points="6 9 12 15 18 9"/>
      </svg>
    </button>

    <div v-if="expanded" class="citation-list slide-in">
      <div
        v-for="(source, idx) in sources"
        :key="idx"
        class="citation-item"
      >
        <div class="citation-index">{{ idx + 1 }}</div>
        <div class="citation-body">
          <div class="citation-source">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
            </svg>
            {{ source.source || '未知来源' }}
            <span v-if="source.score" class="citation-score">
              相似度: {{ (source.score * 100).toFixed(1) }}%
            </span>
          </div>
          <div class="citation-text">{{ source.content }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  sources: { type: Array, default: () => [] },
})

const expanded = ref(false)
</script>

<style scoped>
.source-citation {
  margin-top: 12px;
}

.citation-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  background: none;
  border: none;
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  padding: 4px 0;
  transition: color var(--transition);
}

.citation-toggle:hover {
  color: var(--primary);
}

.chevron {
  transition: transform 0.2s;
}

.chevron.rotated {
  transform: rotate(180deg);
}

.citation-list {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.citation-item {
  display: flex;
  gap: 10px;
  background: var(--bg);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  padding: 10px 12px;
}

.citation-index {
  width: 22px;
  height: 22px;
  min-width: 22px;
  background: var(--primary-light);
  color: var(--primary);
  font-size: 11px;
  font-weight: 700;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.citation-source {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 4px;
  font-weight: 500;
}

.citation-score {
  font-size: 11px;
  color: var(--primary);
  margin-left: 8px;
}

.citation-text {
  font-size: 12px;
  color: var(--text);
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>