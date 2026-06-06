<template>
  <div class="home">
    <!-- 侧边栏 -->
    <aside class="sidebar" :class="{ open: sidebarOpen }">
      <div class="sidebar-header">
        <div class="logo">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
          </svg>
          <span>SmartQA</span>
        </div>
        <button class="btn-new-chat" @click="handleNewChat">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          <span>新对话</span>
        </button>
      </div>

      <div class="history-list">
        <div class="history-label">历史对话</div>
        <div
          v-for="conv in store.conversations"
          :key="conv.conversation_id"
          class="history-item"
          :class="{ active: conv.conversation_id === store.currentConversationId }"
          @click="store.loadConversation(conv.conversation_id)"
        >
          <div class="history-item-text">{{ conv.last_message || '新对话' }}</div>
          <button class="btn-delete" @click.stop="store.removeConversation(conv.conversation_id)" title="删除">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
            </svg>
          </button>
        </div>
        <div v-if="store.conversations.length === 0" class="history-empty">
          暂无历史对话
        </div>
      </div>

      <div class="sidebar-footer">
        <div class="status-dot" :class="{ online: systemOk }"></div>
        <span>{{ systemOk ? '系统就绪' : '连接中...' }}</span>
      </div>
    </aside>

    <!-- 主内容区 -->
    <main class="main-content">
      <!-- 顶部栏 -->
      <header class="topbar">
        <button class="btn-menu" @click="sidebarOpen = !sidebarOpen">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/>
          </svg>
        </button>
        <h1 class="title">智能问数系统</h1>
        <div class="topbar-actions">
          <span class="response-badge" v-if="lastMsg?.responseTimeMs">
            {{ lastMsg.responseTimeMs }}ms
          </span>
        </div>
      </header>

      <!-- 对话区域 -->
      <div class="chat-area" ref="chatAreaRef">
        <!-- 欢迎页 -->
        <div v-if="store.messages.length === 0" class="welcome">
          <div class="welcome-icon">
            <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="var(--primary)" stroke-width="1.5">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
              <line x1="9" y1="10" x2="15" y2="10"/><line x1="12" y1="7" x2="12" y2="13"/>
            </svg>
          </div>
          <h2>智能数据问答助手</h2>
          <p>基于 RAG 架构，支持对中国宏观经济、人口、企业营收、区域GDP等公开数据进行智能问答</p>
          <div class="example-questions">
            <span class="example-label">试试这些问题：</span>
            <button
              v-for="q in exampleQuestions"
              :key="q"
              class="example-btn"
              @click="handleExampleClick(q)"
            >{{ q }}</button>
          </div>
        </div>

        <!-- 消息列表 -->
        <div v-else class="messages">
          <ChatMessage
            v-for="msg in store.messages"
            :key="msg.id"
            :message="msg"
          />
          <!-- 加载状态 -->
          <div v-if="store.isLoading && !store.isStreaming" class="loading-indicator">
            <div class="typing-dots">
              <span></span><span></span><span></span>
            </div>
            <span class="loading-text">正在分析数据...</span>
          </div>
        </div>
      </div>

      <!-- 输入区 -->
      <div class="input-area">
        <ChatInput
          :disabled="store.isLoading || store.isStreaming"
          @send="handleSend"
          @stop="store.stopStream()"
        />
      </div>
    </main>

    <!-- 移动端遮罩 -->
    <div v-if="sidebarOpen" class="mobile-overlay" @click="sidebarOpen = false"></div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { useChatStore } from '../stores/chat'
import { healthCheck } from '../api'
import ChatMessage from '../components/ChatMessage.vue'
import ChatInput from '../components/ChatInput.vue'

const store = useChatStore()
const sidebarOpen = ref(window.innerWidth > 768)
const systemOk = ref(false)
const chatAreaRef = ref(null)

const lastMsg = computed(() => store.lastMessage)

const exampleQuestions = [
  '2024年中国GDP总量是多少？',
  '2023年哪些企业营收超过5000亿元？',
  '中国城镇化率的变化趋势是怎样的？',
  '2023年哪个省的GDP最高？',
  '比较阿里巴巴和腾讯的营收和利润',
]

async function checkHealth() {
  try {
    await healthCheck()
    systemOk.value = true
  } catch {
    systemOk.value = false
  }
}

function handleNewChat() {
  store.newConversation()
}

function handleExampleClick(q) {
  store.send(q)
}

function handleSend(question) {
  store.send(question)
  nextTick(() => scrollToBottom())
}

function scrollToBottom() {
  nextTick(() => {
    const el = chatAreaRef.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

// 监听窗口大小
function handleResize() {
  sidebarOpen.value = window.innerWidth > 768
}

onMounted(() => {
  checkHealth()
  store.loadHistory()
  window.addEventListener('resize', handleResize)
})
</script>

<style scoped>
.home {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

/* ===== 侧边栏 ===== */
.sidebar {
  width: 280px;
  min-width: 280px;
  background: var(--bg-sidebar);
  color: #e2e8f0;
  display: flex;
  flex-direction: column;
  transition: transform var(--transition);
  z-index: 100;
}

.sidebar-header {
  padding: 20px;
  border-bottom: 1px solid rgba(255,255,255,0.08);
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 18px;
  font-weight: 700;
  color: #fff;
  margin-bottom: 16px;
}

.btn-new-chat {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  padding: 10px 16px;
  background: var(--primary);
  color: #fff;
  border: none;
  border-radius: var(--radius-sm);
  font-size: 14px;
  cursor: pointer;
  transition: background var(--transition);
}

.btn-new-chat:hover {
  background: var(--primary-hover);
}

.history-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.history-label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: #64748b;
  padding: 8px 8px 12px;
}

.history-item {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background 0.15s;
  margin-bottom: 2px;
}

.history-item:hover {
  background: rgba(255,255,255,0.06);
}

.history-item.active {
  background: rgba(79, 70, 229, 0.2);
}

.history-item-text {
  flex: 1;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #cbd5e1;
}

.btn-delete {
  background: none;
  border: none;
  color: #64748b;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  opacity: 0;
  transition: opacity 0.15s;
}

.history-item:hover .btn-delete {
  opacity: 1;
}

.btn-delete:hover {
  color: var(--danger);
  background: rgba(239,68,68,0.1);
}

.history-empty {
  font-size: 13px;
  color: #64748b;
  text-align: center;
  padding: 24px 0;
}

.sidebar-footer {
  padding: 16px 20px;
  border-top: 1px solid rgba(255,255,255,0.08);
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #94a3b8;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #64748b;
}

.status-dot.online {
  background: var(--success);
  box-shadow: 0 0 6px rgba(16, 185, 129, 0.5);
}

/* ===== 主内容区 ===== */
.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: var(--bg);
}

.topbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 20px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.btn-menu {
  background: none;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 6px;
  border-radius: 6px;
  display: none;
}

.btn-menu:hover {
  background: var(--bg);
  color: var(--text);
}

.title {
  font-size: 16px;
  font-weight: 600;
  flex: 1;
}

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.response-badge {
  font-size: 12px;
  color: var(--success);
  background: #ecfdf5;
  padding: 4px 10px;
  border-radius: 20px;
  font-weight: 500;
}

/* ===== 对话区域 ===== */
.chat-area {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  scroll-behavior: smooth;
}

/* ===== 欢迎页 ===== */
.welcome {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  text-align: center;
  padding: 40px 20px;
}

.welcome-icon {
  width: 120px;
  height: 120px;
  background: var(--primary-light);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 24px;
}

.welcome h2 {
  font-size: 24px;
  font-weight: 700;
  margin-bottom: 8px;
  color: var(--text);
}

.welcome p {
  font-size: 14px;
  color: var(--text-secondary);
  max-width: 480px;
  margin-bottom: 32px;
  line-height: 1.7;
}

.example-questions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
  max-width: 600px;
}

.example-label {
  width: 100%;
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.example-btn {
  padding: 8px 16px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 20px;
  font-size: 13px;
  color: var(--text);
  cursor: pointer;
  transition: all var(--transition);
}

.example-btn:hover {
  border-color: var(--primary);
  color: var(--primary);
  background: var(--primary-light);
}

/* ===== 消息列表 ===== */
.messages {
  max-width: 800px;
  margin: 0 auto;
}

.loading-indicator {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 20px;
}

.typing-dots {
  display: flex;
  gap: 4px;
}

.typing-dots span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--primary);
  animation: pulse 1.4s infinite ease-in-out;
}

.typing-dots span:nth-child(2) { animation-delay: 0.2s; }
.typing-dots span:nth-child(3) { animation-delay: 0.4s; }

.loading-text {
  font-size: 13px;
  color: var(--text-secondary);
}

/* ===== 输入区 ===== */
.input-area {
  padding: 16px 20px 20px;
  background: var(--bg-card);
  border-top: 1px solid var(--border);
  flex-shrink: 0;
}

/* ===== 移动端遮罩 ===== */
.mobile-overlay {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.4);
  z-index: 99;
}

/* ===== 响应式 ===== */
@media (max-width: 768px) {
  .sidebar {
    position: fixed;
    left: 0;
    top: 0;
    bottom: 0;
    transform: translateX(-100%);
    box-shadow: var(--shadow-lg);
  }

  .sidebar.open {
    transform: translateX(0);
  }

  .btn-menu {
    display: block;
  }

  .mobile-overlay {
    display: block;
  }

  .welcome h2 {
    font-size: 20px;
  }

  .chat-area {
    padding: 12px;
  }

  .input-area {
    padding: 12px;
  }
}
</style>