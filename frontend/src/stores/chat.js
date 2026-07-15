import { defineStore } from 'pinia'
import { ref, computed, reactive } from 'vue'
import {
  sendMessage,
  sendMessageStream,
  getHistory,
  getConversation,
  deleteConversation,
  listDatasources,
} from '../api'

export const useChatStore = defineStore('chat', () => {
  const currentConversationId = ref(null)
  const messages = ref([])
  const isLoading = ref(false)
  const streamingContent = ref('')
  const isStreaming = ref(false)
  const chatMode = ref('pipeline')
  const datasourceId = ref(null)
  const datasources = ref([])
  const recommendedQuestions = ref([])
  const conversations = ref([])

  let streamController = null

  const lastMessage = computed(() =>
    messages.value.length > 0 ? messages.value[messages.value.length - 1] : null
  )

  function setChatMode(mode) {
    chatMode.value = mode === 'agent' ? 'agent' : 'pipeline'
  }

  function setDatasourceId(id) {
    datasourceId.value = id || null
  }

  async function loadDatasources() {
    try {
      const { data } = await listDatasources()
      datasources.value = data.items || []
      if (!datasourceId.value) {
        const def = datasources.value.find((d) => d.is_default)
        datasourceId.value = def?.id || datasources.value[0]?.id || null
      }
    } catch {
      datasources.value = []
    }
  }

  function newConversation() {
    currentConversationId.value = null
    messages.value = []
    streamingContent.value = ''
    isStreaming.value = false
    recommendedQuestions.value = []
  }

  /** 更新流式消息内容并触发 UI 刷新（兼容 Pinia 代理） */
  function applyStreamContent(aiMsg, text) {
    const cleaned = (text || '').replace(/```chart_data\n[\s\S]*?\n```/g, '')
    aiMsg.content = cleaned
    // 触发数组响应式，确保 ChatMessage 重渲染
    const idx = messages.value.findIndex((m) => m === aiMsg || m.id === aiMsg.id)
    if (idx !== -1) {
      messages.value[idx] = aiMsg
    }
  }

  async function send(question) {
    messages.value.push({
      id: Date.now().toString(),
      role: 'user',
      content: question,
      timestamp: new Date().toISOString(),
    })

    isLoading.value = true

    try {
      const { data } = await sendMessage(
        question,
        currentConversationId.value,
        datasourceId.value,
      )
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
        toolCalls: data.tool_calls || [],
        mode: data.mode || 'pipeline',
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

    // 必须用 reactive，否则原地改 content 不会触发视图更新
    const aiMsg = reactive({
      id: `tmp-${Date.now()}`,
      role: 'assistant',
      content: '',
      question: question,
      sources: [],
      toolCalls: [],
      mode: chatMode.value,
      isStreaming: true,
      chartData: null,
      hasNumericData: false,
      sql: '',
      sqlResult: null,
      responseTimeMs: 0,
      timestamp: new Date().toISOString(),
    })
    messages.value.push(aiMsg)

    try {
      const { response, controller } = sendMessageStream(
        question,
        currentConversationId.value,
        chatMode.value,
        datasourceId.value,
      )
      streamController = controller

      const res = await response
      if (!res.ok) {
        let detail = ''
        try {
          const errBody = await res.json()
          detail = errBody?.detail?.message || errBody?.detail || errBody?.message || ''
        } catch {}
        throw new Error(detail || `请求失败 (${res.status})`)
      }

      if (!res.body) {
        throw new Error('浏览器不支持流式读取（ReadableStream 不可用）')
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let accumulated = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        // SSE 事件以空行分隔；兼容 \r\n
        const parts = buffer.split(/\r?\n/)
        buffer = parts.pop() || ''

        for (const rawLine of parts) {
          const line = rawLine.trimEnd()
          if (!line.startsWith('data:')) continue
          // 兼容 "data: {...}" 与 "data:{...}"
          const payload = line.slice(5).trimStart()
          if (!payload || payload === '[DONE]') continue

          let data
          try {
            data = JSON.parse(payload)
          } catch {
            // 半包 JSON，拼回 buffer 等下一帧（极少见，payload 通常完整）
            continue
          }

          if (data.recommended_questions) {
            recommendedQuestions.value = data.recommended_questions
          }

          // Pipeline / Agent fallback 文本块
          if (
            typeof data.chunk === 'string' &&
            data.chunk.length > 0 &&
            data.type !== 'tool_start' &&
            data.type !== 'tool_result'
          ) {
            accumulated += data.chunk
            streamingContent.value = accumulated
            applyStreamContent(aiMsg, accumulated)
          }

          if (data.type === 'tool_start') {
            if (!aiMsg.toolCalls) aiMsg.toolCalls = []
            aiMsg.toolCalls.push({
              tool: data.tool,
              args: data.args || {},
              result_preview: '',
              status: 'running',
            })
          }

          if (data.type === 'tool_result') {
            if (!aiMsg.toolCalls) aiMsg.toolCalls = []
            const last = [...aiMsg.toolCalls]
              .reverse()
              .find((t) => t.tool === data.tool && t.status === 'running')
            if (last) {
              last.result_preview = data.result_preview || ''
              last.status = 'done'
            } else {
              aiMsg.toolCalls.push({
                tool: data.tool,
                args: {},
                result_preview: data.result_preview || '',
                status: 'done',
              })
            }
          }

          if (data.done === true || data.type === 'done') {
            const serverMsgId = data.message_id || data.id
            if (serverMsgId) {
              aiMsg.id = serverMsgId
            }
            currentConversationId.value = data.conversation_id || currentConversationId.value
            aiMsg.sources = data.sources || aiMsg.sources || []
            aiMsg.sql = data.sql || aiMsg.sql || ''
            aiMsg.sqlResult = data.sql_result || aiMsg.sqlResult || null
            aiMsg.responseTimeMs = data.response_time_ms || 0
            aiMsg.chartData = data.chart_data || null
            aiMsg.hasNumericData = data.has_numeric_data || !!data.chart_data
            aiMsg.mode = data.mode || chatMode.value
            if (data.tool_calls?.length) {
              aiMsg.toolCalls = data.tool_calls
            }
            // Agent 常在 done 才给完整 answer
            if (typeof data.answer === 'string' && data.answer.length > 0) {
              accumulated = data.answer
              streamingContent.value = accumulated
            }
            applyStreamContent(aiMsg, accumulated || aiMsg.content)
            aiMsg.isStreaming = false
          }

          if (data.error) {
            const errMsg =
              typeof data.error === 'object'
                ? data.error.message || data.error.detail || JSON.stringify(data.error)
                : String(data.error)
            aiMsg.content = `错误: ${errMsg}`
            aiMsg.isError = true
            aiMsg.isStreaming = false
          }
        }
      }

      aiMsg.isStreaming = false
      if (accumulated && !aiMsg.content) {
        applyStreamContent(aiMsg, accumulated)
      }
    } catch (err) {
      if (err.name !== 'AbortError') {
        aiMsg.content = `流式请求中断: ${err.message}`
        aiMsg.isError = true
        aiMsg.isStreaming = false
      }
    } finally {
      isStreaming.value = false
      streamingContent.value = ''
      streamController = null
      await loadHistory()
    }
  }

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

  async function loadHistory() {
    try {
      const { data } = await getHistory()
      conversations.value = data.conversations || []
    } catch {}
  }

  async function loadConversation(convId) {
    try {
      const { data } = await getConversation(convId)
      currentConversationId.value = convId
      messages.value = []
      for (const msg of data.messages || []) {
        messages.value.push({
          id: `${msg.id}_user`,
          role: 'user',
          content: msg.question,
          timestamp: msg.created_at,
        })
        messages.value.push({
          id: msg.id,
          role: 'assistant',
          content: msg.answer,
          question: msg.question,
          sql: msg.sql || '',
          sqlResult: msg.sql_result || null,
          sources: msg.sources || [],
          chartData: msg.chart_data || null,
          toolCalls: msg.tool_calls || [],
          mode: msg.mode || 'pipeline',
          responseTimeMs: msg.response_time_ms || 0,
          timestamp: msg.created_at,
        })
      }
    } catch {
      console.error('加载对话失败')
    }
  }

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
    chatMode,
    datasourceId,
    datasources,
    recommendedQuestions,
    conversations,
    lastMessage,
    setChatMode,
    setDatasourceId,
    loadDatasources,
    newConversation,
    send,
    sendStream,
    stopStream,
    loadHistory,
    loadConversation,
    removeConversation,
  }
})
