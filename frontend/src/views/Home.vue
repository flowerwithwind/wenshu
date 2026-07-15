<template>
  <div class="home">
    <!-- 会话侧栏 -->
    <aside class="sidebar" :class="{ open: sidebarOpen }">
      <div class="sidebar-header">
        <button class="btn-new-chat" @click="handleNewChat">
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
          >
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
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
          :class="{
            active: conv.conversation_id === store.currentConversationId,
          }"
          @click="store.loadConversation(conv.conversation_id)"
        >
          <div class="history-item-text">
            {{ conv.last_message || "新对话" }}
          </div>
          <button
            class="btn-delete"
            @click.stop="store.removeConversation(conv.conversation_id)"
            title="删除"
          >
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
            >
              <polyline points="3 6 5 6 21 6" />
              <path
                d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"
              />
            </svg>
          </button>
        </div>
        <div v-if="store.conversations.length === 0" class="history-empty">
          暂无历史对话
        </div>
      </div>

      <div class="sidebar-footer">
        <div class="status-dot" :class="{ online: systemOk }"></div>
        <span>{{ systemOk ? "系统就绪" : "连接中..." }}</span>
      </div>

      <div class="sidebar-upload">
        <FileUpload />
      </div>
    </aside>

    <!-- 主内容区 -->
    <main class="main-content">
      <!-- 顶部栏 -->
      <header class="topbar">
        <button class="btn-menu" @click="sidebarOpen = !sidebarOpen">
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
          >
            <line x1="3" y1="12" x2="21" y2="12" />
            <line x1="3" y1="6" x2="21" y2="6" />
            <line x1="3" y1="18" x2="21" y2="18" />
          </svg>
        </button>
        <h1 class="title">智能问数</h1>
        <div class="topbar-center">
          <div class="mode-switch" title="切换查询引擎">
            <button
              class="mode-btn"
              :class="{ active: store.chatMode === 'pipeline' }"
              :disabled="store.isStreaming || store.isLoading"
              @click="store.setChatMode('pipeline')"
            >
              Pipeline
            </button>
            <button
              class="mode-btn"
              :class="{ active: store.chatMode === 'agent' }"
              :disabled="store.isStreaming || store.isLoading"
              @click="store.setChatMode('agent')"
            >
              Agent
            </button>
          </div>
          <select
            class="ds-select"
            :disabled="store.isStreaming || store.isLoading"
            :value="store.datasourceId || ''"
            @change="onDatasourceChange"
            title="选择数据源"
          >
            <option v-for="ds in store.datasources" :key="ds.id" :value="ds.id">
              {{ ds.name }}{{ ds.is_default ? "（默认）" : "" }}
            </option>
          </select>
          <ModelSelector
            :disabled="store.isStreaming || store.isLoading"
            @changed="onModelChanged"
          />
        </div>
        <div class="topbar-actions">
          <span
            class="response-badge"
            v-if="lastMsg?.responseTimeMs && !store.isStreaming"
          >
            {{ lastMsg.responseTimeMs }}ms
          </span>
        </div>
      </header>

      <!-- 对话区域 -->
      <div class="chat-area" ref="chatAreaRef">
        <!-- 欢迎页 -->
        <div v-if="store.messages.length === 0" class="welcome">
          <div class="welcome-icon">
            <svg
              width="64"
              height="64"
              viewBox="0 0 24 24"
              fill="none"
              stroke="var(--primary)"
              stroke-width="1.5"
            >
              <path
                d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"
              />
              <line x1="9" y1="10" x2="15" y2="10" />
              <line x1="12" y1="7" x2="12" y2="13" />
            </svg>
          </div>
          <h2>智能问数助手</h2>
          <p>
            基于 NL2SQL + RAG + ReAct Agent。当前数据源：
            <strong>{{ currentDsName }}</strong>
            — 用自然语言查询、分析并可视化（多数据源可切换）
          </p>
          <div class="example-questions">
            <span class="example-label">试试这些问题：</span>
            <button
              v-for="q in exampleQuestions"
              :key="q"
              class="example-btn"
              @click="handleExampleClick(q)"
            >
              {{ q }}
            </button>
          </div>
        </div>

        <!-- 消息列表 -->
        <div v-else class="messages">
          <template v-for="msg in store.messages" :key="msg.id">
            <!-- 用户消息 / 已有内容的助手消息 -->
            <ChatMessage
              v-if="
                !(msg.role === 'assistant' && msg.isStreaming && !msg.content)
              "
              :message="msg"
            />
          </template>

          <!-- 等待模型输出首 token：思考中 -->
          <ThinkingIndicator
            v-if="isThinking"
            :title="thinkingTitle"
            :subtitle="thinkingSubtitle"
          />

          <!-- 非流式加载 -->
          <div
            v-if="store.isLoading && !store.isStreaming"
            class="loading-indicator"
          >
            <div class="typing-dots">
              <span></span><span></span><span></span>
            </div>
            <span class="loading-text">正在分析数据...</span>
          </div>

          <!-- 推荐问题 -->
          <div
            v-if="store.recommendedQuestions.length > 0 && !store.isStreaming"
            class="recommended-questions"
          >
            <div class="recommend-label">换个问题试试：</div>
            <button
              v-for="q in store.recommendedQuestions"
              :key="q"
              class="recommend-btn"
              @click="handleExampleClick(q)"
            >
              {{ q }}
            </button>
          </div>
        </div>
      </div>

      <!-- 滚动到底部按钮 -->
      <button
        v-if="showScrollBtn"
        class="scroll-bottom-btn"
        @click="scrollToBottom"
        title="滚动到底部"
      >
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      <!-- 输入区 -->
      <div class="input-area">
        <ChatInput
          :disabled="store.isLoading || store.isStreaming"
          :is-streaming="store.isStreaming"
          @send="handleSend"
          @stop="store.stopStream()"
        />
      </div>
    </main>

    <!-- 移动端遮罩 -->
    <div
      v-if="sidebarOpen"
      class="mobile-overlay"
      @click="sidebarOpen = false"
    ></div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch } from "vue";
import { useChatStore } from "../stores/chat";
import { healthCheck } from "../api";
import ChatMessage from "../components/ChatMessage.vue";
import ChatInput from "../components/ChatInput.vue";
import FileUpload from "../components/FileUpload.vue";
import ThinkingIndicator from "../components/ThinkingIndicator.vue";
import ModelSelector from "../components/ModelSelector.vue";
import { storeToRefs } from "pinia";

const store = useChatStore();
const { isStreaming, messages, chatMode } = storeToRefs(store);
const sidebarOpen = ref(window.innerWidth > 900);
const systemOk = ref(false);
const chatAreaRef = ref(null);
const modelLabel = ref("DeepSeek");
const showScrollBtn = ref(false);

const lastMsg = computed(() => store.lastMessage);

/** 已发出请求、尚未收到任何正文 chunk */
const isThinking = computed(() => {
  const m = lastMsg.value;
  return !!(
    store.isStreaming &&
    m &&
    m.role === "assistant" &&
    m.isStreaming &&
    !(m.content && String(m.content).trim())
  );
});

const thinkingTitle = computed(() =>
  chatMode.value === "agent" ? "Agent 正在思考" : "模型正在思考",
);

const thinkingSubtitle = computed(() => {
  const name = modelLabel.value || "DeepSeek";
  return chatMode.value === "agent"
    ? `${name} · 规划工具调用与分析步骤…`
    : `${name} · 理解问题、生成 SQL 并撰写回答…`;
});

function onModelChanged(data) {
  modelLabel.value = data?.label || data?.model || "DeepSeek";
}

function onDatasourceChange(e) {
  store.setDatasourceId(e.target.value);
}

// 流式输出时跟随滚动
watch(
  () => [isStreaming.value, lastMsg.value?.content, isThinking.value],
  () => {
    if (isStreaming.value || isThinking.value) scrollToBottom();
  },
);
watch(
  () => messages.value.length,
  () => scrollToBottom(),
);

/** 监听聊天区域滚动，显示/隐藏“回到底部”按钮 */
function handleChatScroll() {
  const el = chatAreaRef.value;
  if (!el) return;
  const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
  showScrollBtn.value = !atBottom && messages.value.length > 0;
}

const currentDsName = computed(() => {
  const id = store.datasourceId;
  const ds = (store.datasources || []).find((d) => d.id === id);
  return ds?.name || "默认数据源";
});

/** 示例问题随数据源名称做轻量适配（通用问法，避免写死电商） */
const exampleQuestions = computed(() => {
  const name = (currentDsName.value || "").toLowerCase();
  if (name.includes("医院") || name.includes("hospital")) {
    return [
      "有哪些表？",
      "患者一共有多少人？",
      "各专科的预约量排名？",
      "预约状态分布如何？",
      "账单金额按状态汇总？",
    ];
  }
  if (name.includes("物流") || name.includes("logistic")) {
    return [
      "有哪些表？",
      "行程一共有多少条？",
      "各 trip_status 的数量？",
      "按月统计行程量趋势？",
      "行程与运单关联后有多少行？",
    ];
  }
  if (name.includes("电商") || name.includes("演示")) {
    return [
      "2024年各月销售额趋势是怎样的？",
      "销售额排名前5的省份是哪些？",
      "各会员等级的消费总额对比如何？",
      "有折扣的订单占比是多少？",
      "退款率最高的品类是什么？",
    ];
  }
  return [
    "当前数据源有哪些表？",
    "最大的表大概有多少行？",
    "挑一张表按某个分类字段做数量统计",
    "有没有可以按月份看的趋势？",
    "两张有关联的表 JOIN 后怎么统计？",
  ];
});

async function checkHealth() {
  try {
    await healthCheck();
    systemOk.value = true;
  } catch {
    systemOk.value = false;
  }
}

function handleNewChat() {
  store.newConversation();
}

function handleExampleClick(q) {
  store.sendStream(q);
}

function handleSend(question) {
  store.sendStream(question);
  nextTick(() => scrollToBottom());
}

function scrollToBottom() {
  nextTick(() => {
    const el = chatAreaRef.value;
    if (el) el.scrollTop = el.scrollHeight;
  });
}

// 监听窗口大小
function handleResize() {
  sidebarOpen.value = window.innerWidth > 768;
}

onMounted(() => {
  checkHealth();
  store.loadHistory();
  store.loadDatasources();
  window.addEventListener("resize", handleResize);
  // 监听聊天区域滚动
  chatAreaRef.value?.addEventListener("scroll", handleChatScroll);
});
</script>

<style scoped>
.home {
  display: flex;
  flex: 1;
  min-height: 0;
  height: 100%;
  max-height: 100%;
  overflow: hidden;
}

.ds-select {
  max-width: 200px;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 6px 10px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text);
  background: var(--bg-card);
  outline: none;
  transition: border-color var(--transition), box-shadow var(--transition);
}

.ds-select:focus {
  border-color: var(--border-focus);
  box-shadow: 0 0 0 3px var(--primary-muted);
}

/* ===== 侧边栏 ===== */
.sidebar {
  width: 280px;
  min-width: 280px;
  height: 100%;
  background: var(--bg-sidebar);
  color: #e2e8f0;
  display: flex;
  flex-direction: column;
  transition: transform var(--transition);
  z-index: 100;
  overflow: hidden;
}

.sidebar-header {
  padding: 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 18px;
  font-weight: 700;
  color: #fff;
  margin-bottom: 16px;
  letter-spacing: -0.02em;
}

.btn-new-chat {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  padding: 11px 16px;
  background: var(--brand-gradient);
  color: var(--text-on-brand);
  border: none;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all var(--transition);
  box-shadow: 0 4px 14px rgba(79, 70, 229, 0.35);
}

.btn-new-chat:hover {
  filter: brightness(1.06);
  transform: translateY(-1px);
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
  background: rgba(255, 255, 255, 0.06);
}

.history-item.active {
  background: var(--primary-muted);
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
  background: rgba(239, 68, 68, 0.1);
}

.history-empty {
  font-size: 13px;
  color: #64748b;
  text-align: center;
  padding: 24px 0;
}

.sidebar-footer {
  padding: 16px 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
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

.sidebar-upload {
  padding: 0 12px 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.sidebar-km {
  padding: 0 12px 12px;
}

.btn-knowledge {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: 100%;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.06);
  color: #94a3b8;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: var(--radius-sm);
  font-size: 12px;
  cursor: pointer;
  transition: all var(--transition);
}

.btn-knowledge:hover {
  background: rgba(79, 70, 229, 0.15);
  color: #e2e8f0;
  border-color: var(--primary);
}

/* ===== 主内容区 ===== */
.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  height: 100%;
  position: relative;
  position: relative; /* 为滚动按钮提供定位上下文 */
  overflow: hidden;
  background: var(--bg);
}

.topbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 20px;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
  z-index: 5;
}

.topbar-center {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
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

.mode-switch {
  display: inline-flex;
  align-items: center;
  background: #f1f5f9;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 3px;
}
.mode-btn {
  border: none;
  background: transparent;
  color: #64748b;
  font-size: 12px;
  font-weight: 600;
  padding: 6px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
}
.mode-btn.active {
  background: #fff;
  color: var(--primary);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}
.mode-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.title {
  font-size: 16px;
  font-weight: 700;
  flex: 1;
  letter-spacing: -0.02em;
  background: linear-gradient(90deg, #0f172a, #334155);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.dashboard-link {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  background: var(--primary-light);
  color: var(--primary);
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  text-decoration: none;
  transition: all var(--transition);
}

.dashboard-link:hover {
  background: var(--primary);
  color: #fff;
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

/* ===== 对话区域（仅此区域滚动，输入区始终贴底） ===== */
.chat-area {
  flex: 1 1 auto;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  padding: 24px 20px 12px;
  scroll-behavior: smooth;
  background:
    radial-gradient(
      ellipse 80% 50% at 50% -20%,
      rgba(79, 70, 229, 0.07),
      transparent
    ),
    var(--bg);
}

.messages {
  max-width: 820px;
  margin: 0 auto;
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
  width: 112px;
  height: 112px;
  background: linear-gradient(145deg, #eef2ff, #e0e7ff);
  border-radius: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 24px;
  box-shadow: 0 12px 40px rgba(79, 70, 229, 0.15);
}

.welcome h2 {
  font-size: 26px;
  font-weight: 800;
  margin-bottom: 10px;
  color: var(--text);
  letter-spacing: -0.03em;
}

.welcome p {
  font-size: 14px;
  color: var(--text-secondary);
  max-width: 480px;
  margin-bottom: 32px;
  line-height: 1.75;
}

.example-questions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: center;
  max-width: 640px;
}

.example-label {
  width: 100%;
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 4px;
  font-weight: 500;
}

.example-btn {
  padding: 10px 16px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 14px;
  font-size: 13px;
  color: var(--text);
  cursor: pointer;
  transition: all var(--transition);
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}

.example-btn:hover {
  border-color: #a5b4fc;
  background: #eef2ff;
  color: #4338ca;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(79, 70, 229, 0.12);
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

.typing-dots span:nth-child(2) {
  animation-delay: 0.2s;
}
.typing-dots span:nth-child(3) {
  animation-delay: 0.4s;
}

.loading-text {
  font-size: 13px;
  color: var(--text-secondary);
}

/* ===== 推荐问题 ===== */
.recommended-questions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 12px 0;
  margin-top: 4px;
}

.recommend-label {
  width: 100%;
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 2px;
}

.recommend-btn {
  padding: 6px 14px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 16px;
  font-size: 13px;
  color: var(--text);
  cursor: pointer;
  transition: all var(--transition);
}

.recommend-btn:hover {
  border-color: var(--primary);
  color: var(--primary);
  background: var(--primary-light);
}

/* ===== 滚动到底部按钮 ===== */
.scroll-bottom-btn {
  position: absolute;
  bottom: 88px;
  right: 24px;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: #fff;
  border: 1px solid var(--border);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  z-index: 20;
  transition: all 0.15s;
  animation: fadeIn 0.2s ease;
}

.scroll-bottom-btn:hover {
  border-color: var(--primary);
  color: var(--primary);
  box-shadow: 0 4px 16px rgba(79, 70, 229, 0.15);
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* ===== 输入区：固定在主内容区底部，不随消息滚动 ===== */
.input-area {
  flex: 0 0 auto;
  padding: 14px 20px 18px;
  background: linear-gradient(180deg, rgba(248, 250, 252, 0.92), #fff);
  border-top: 1px solid var(--border);
  z-index: 10;
  /* 底部安全区（移动端刘海屏） */
  padding-bottom: max(18px, env(safe-area-inset-bottom, 0px));
}

/* ===== 移动端遮罩 ===== */
.mobile-overlay {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  z-index: 99;
}

/* ===== 响应式 ===== */

/* 平板：侧栏默认收起 */
@media (max-width: 1024px) {
  .sidebar {
    width: 260px;
    min-width: 260px;
  }
  .topbar-center {
    flex-wrap: wrap;
    gap: 6px;
  }
}

/* 移动端 */
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

  .topbar {
    padding: 10px 12px;
  }

  .ds-select {
    max-width: 140px;
  }
}

/* 小屏手机 */
@media (max-width: 640px) {
  .sidebar {
    width: 100%;
    min-width: 100%;
  }

  .welcome p {
    font-size: 13px;
  }

  .example-btn {
    font-size: 12px;
    padding: 8px 12px;
  }

  .topbar-center {
    display: none;
  }

  .scroll-bottom-btn {
    bottom: 76px;
    right: 16px;
  }
}
</style>
