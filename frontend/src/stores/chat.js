import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { sendMessage, sendMessageStream, getHistory, getConversation, deleteConversation } from '../api'

export const useChatStore = defineStore('chat', () => {
  // 当前对话
  const currentConversationId = ref(null)
  const messages = ref([])
  const isLoading = ref(false)
  const streamingContent = ref('')
  const isStreaming = ref(false)

  // 推荐问题
  const recommendedQuestions = ref([])

  // 历史对话列表
  const conversations = ref([])

  // 流式控制器
  let streamController = null

  const lastMessage = computed(() =>
    messages.value.length > 0 ? messages.value[messages.value.length - 1] : null
  )

  // 新建对话
  function newConversation() {
    currentConversationId.value = null
    messages.value = []
    streamingContent.value = ''
    isStreaming.value = false
    recommendedQuestions.value = []
  }

  // 发送消息（非流式）
  async function send(question) {
    messages.value.push({
      id: Date.now().toString(),
      role: 'user',
      content: question,
      timestamp: new Date().toISOString(),
    })

    isLoading.value = true

    try {
      const { data } = await sendMessage(question, currentConversationId.value)
      currentConversationId.value = data.conversation_id

      messages.value.push({
        id: data.id,
        role: 'assistant',
        content: data.answer,
        question: question,
        sources: data.sources || [],
        chartData: data.chart_data,
        hasNumericData: data.has_numeric_data,
        responseTimeMs: data.response_time_ms,
        sql: data.sql || '',
        sqlResult: data.sql_result || null,
        timestamp: data.created_at,
      })
    } catch (err) {
      messages.value.push({
        id: Date.now().toString(),
        role: 'assistant',
        content: `错误: ${err.message || '请求失败，请稍后重试'}`,
        isError: true,
        timestamp: new Date().toISOString(),
      })
    } finally {
      isLoading.value = false
    }

    await loadHistory()
  }

  // 流式发送消息
  async function sendStream(question) {
    recommendedQuestions.value = []

    messages.value.push({
      id: Date.now().toString(),
      role: 'user',
      content: question,
      question: question,
      timestamp: new Date().toISOString(),
    })

    isStreaming.value = true
    streamingContent.value = ''

    // 添加占位消息
    const aiMsgId = (Date.now() + 1).toString()
    messages.value.push({
      id: aiMsgId,
      role: 'assistant',
      content: '',
      question: question,
      sources: [],
      isStreaming: true,
      timestamp: new Date().toISOString(),
    })

    try {
      const { response, controller } = sendMessageStream(question, currentConversationId.value)
      streamController = controller

      const reader = (await response).body.getReader()
      const decoder = new TextDecoder()

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const text = decoder.decode(value, { stream: true })
        const lines = text.split('\n')

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              if (data.chunk) {
                streamingContent.value += data.chunk
                const msg = messages.value.find(m => m.id === aiMsgId)
                if (msg) msg.content = streamingContent.value
              }
              if (data.done) {
                currentConversationId.value = data.conversation_id
                const msg = messages.value.find(m => m.id === aiMsgId)
                if (msg) {
                  msg.sources = data.sources || []
                  msg.sql = data.sql || ''
                  msg.sqlResult = data.sql_result || null
                  msg.responseTimeMs = data.response_time_ms || 0
                  msg.chartData = data.chart_data || null
                  msg.hasNumericData = data.has_numeric_data || false
                  // 从回答内容中移除 chart_data 代码块
                  msg.content = msg.content.replace(/```chart_data\n[\s\S]*?\n```/g, '').trim()
                }
              }
              if (data.recommended_questions) {
                recommendedQuestions.value = data.recommended_questions
              }
            } catch {}
          }
        }
      }

      const msg = messages.value.find(m => m.id === aiMsgId)
      if (msg) msg.isStreaming = false
    } catch (err) {
      if (err.name !== 'AbortError') {
        const msg = messages.value.find(m => m.id === aiMsgId)
        if (msg) {
          msg.content = `流式请求中断: ${err.message}`
          msg.isError = true
          msg.isStreaming = false
        }
      }
    } finally {
      isStreaming.value = false
      streamingContent.value = ''
      await loadHistory()
    }
  }

  // 停止流式输出
  function stopStream() {
    if (streamController) {
      streamController.abort()
      streamController = null
      isStreaming.value = false
      recommendedQuestions.value = []
      const lastMsg = messages.value[messages.value.length - 1]
      if (lastMsg && lastMsg.isStreaming) {
        lastMsg.isStreaming = false
      }
    }
  }

  // 加载历史对话列表
  async function loadHistory() {
    try {
      const { data } = await getHistory()
      conversations.value = data.conversations || []
    } catch {}
  }

  // 加载指定对话
  async function loadConversation(convId) {
    try {
      const { data } = await getConversation(convId)
      currentConversationId.value = convId
      messages.value = []
      for (const msg of data.messages || []) {
        // 用户消息
        messages.value.push({
          id: msg.id,
          role: 'user',
          content: msg.question,
          timestamp: msg.created_at,
        })
        // AI 回复
        messages.value.push({
          id: (msg.id || '') + '_reply',
          role: 'assistant',
          content: msg.answer,
          question: msg.question,
          sql: msg.sql || '',
          sqlResult: msg.sql_result || null,
          sources: msg.sources || [],
          timestamp: msg.created_at,
        })
      }
    } catch {
      console.error('加载对话失败')
    }
  }

  // 删除对话
  async function removeConversation(convId) {
    try {
      await deleteConversation(convId)
      if (currentConversationId.value === convId) {
        newConversation()
      }
      await loadHistory()
    } catch {}
  }

  return {
    currentConversationId,
    messages,
    isLoading,
    streamingContent,
    isStreaming,
    recommendedQuestions,
    conversations,
    lastMessage,
    newConversation,
    send,
    sendStream,
    stopStream,
    loadHistory,
    loadConversation,
    removeConversation,
  }
})