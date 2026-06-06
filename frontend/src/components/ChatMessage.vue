<template>
  <div class="chat-message" :class="[message.role, { error: message.isError }]">
    <!-- 头像 -->
    <div class="msg-avatar">
      <template v-if="message.role === 'user'">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
          <circle cx="12" cy="7" r="4"/>
        </svg>
      </template>
      <template v-else>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/>
        </svg>
      </template>
    </div>

    <!-- 消息内容 -->
    <div class="msg-body">
      <div class="msg-header">
        <span class="msg-role">{{ message.role === 'user' ? '你' : 'SmartQA' }}</span>
        <span class="msg-time" v-if="message.timestamp">
          {{ formatTime(message.timestamp) }}
        </span>
        <span class="msg-time ms" v-if="message.responseTimeMs">
          {{ message.responseTimeMs }}ms
        </span>
      </div>

      <div class="msg-content" v-html="renderedContent"></div>

      <!-- 流式光标 -->
      <span v-if="message.isStreaming" class="stream-cursor">|</span>

      <!-- 数据图表 -->
      <DataChart
        v-if="message.chartData"
        :chartData="message.chartData"
      />

      <!-- 来源引用 -->
      <SourceCitation
        v-if="message.sources && message.sources.length > 0"
        :sources="message.sources"
      />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import MarkdownIt from 'markdown-it'
import DataChart from './DataChart.vue'
import SourceCitation from './SourceCitation.vue'

const props = defineProps({
  message: { type: Object, required: true },
})

const md = new MarkdownIt({
  html: false,
  breaks: true,
  linkify: true,
})

const renderedContent = computed(() => {
  try {
    return md.render(props.message.content || '')
  } catch {
    return props.message.content
  }
})

function formatTime(ts) {
  try {
    const d = new Date(ts)
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  } catch {
    return ''
  }
}
</script>

<style scoped>
.chat-message {
  display: flex;
  gap: 12px;
  padding: 16px 0;
  animation: fadeIn 0.3s ease;
}

.chat-message + .chat-message {
  border-top: 1px solid #f1f5f9;
}

.chat-message.user {
  flex-direction: row;
}

.chat-message.assistant {
  flex-direction: row;
}

.chat-message.error .msg-content {
  color: var(--danger);
}

.msg-avatar {
  width: 36px;
  height: 36px;
  min-width: 36px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.user .msg-avatar {
  background: var(--primary-light);
  color: var(--primary);
}

.assistant .msg-avatar {
  background: #ecfdf5;
  color: var(--success);
}

.error .msg-avatar {
  background: #fef2f2;
  color: var(--danger);
}

.msg-body {
  flex: 1;
  min-width: 0;
}

.msg-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.msg-role {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
}

.msg-time {
  font-size: 11px;
  color: var(--text-secondary);
}

.msg-time.ms {
  color: var(--success);
  font-weight: 500;
}

.msg-content {
  font-size: 14px;
  line-height: 1.8;
  color: var(--text);
  word-wrap: break-word;
}

.msg-content :deep(p) {
  margin-bottom: 8px;
}

.msg-content :deep(p:last-child) {
  margin-bottom: 0;
}

.msg-content :deep(code) {
  background: #f1f5f9;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.msg-content :deep(pre) {
  background: #1e293b;
  color: #e2e8f0;
  padding: 12px 16px;
  border-radius: var(--radius-sm);
  overflow-x: auto;
  margin: 8px 0;
}

.msg-content :deep(pre code) {
  background: none;
  padding: 0;
  color: inherit;
}

.msg-content :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 8px 0;
}

.msg-content :deep(th),
.msg-content :deep(td) {
  border: 1px solid var(--border);
  padding: 8px 12px;
  text-align: left;
  font-size: 13px;
}

.msg-content :deep(th) {
  background: var(--bg);
  font-weight: 600;
}

.msg-content :deep(ul),
.msg-content :deep(ol) {
  padding-left: 20px;
  margin: 4px 0;
}

.msg-content :deep(li) {
  margin-bottom: 2px;
}

.msg-content :deep(strong) {
  font-weight: 600;
}

.stream-cursor {
  display: inline-block;
  animation: pulse 1s infinite;
  color: var(--primary);
  font-weight: bold;
  margin-left: 2px;
}
</style>