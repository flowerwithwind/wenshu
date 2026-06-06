import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
  headers: { 'Content-Type': 'application/json' },
})

// 健康检查
export const healthCheck = () => api.get('/health')

// 发送问题（非流式）
export const sendMessage = (question, conversationId = null) =>
  api.post('/chat', { question, conversation_id: conversationId })

// 流式发送问题
export const sendMessageStream = (question, conversationId = null) => {
  const controller = new AbortController()
  const response = fetch('/api/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, conversation_id: conversationId }),
    signal: controller.signal,
  })
  return { response, controller }
}

// 获取历史列表
export const getHistory = () => api.get('/history')

// 获取对话详情
export const getConversation = (convId) => api.get(`/history/${convId}`)

// 删除对话
export const deleteConversation = (convId) => api.delete(`/history/${convId}`)

// 重建索引
export const rebuildIndex = () => api.post('/rebuild-index')

// 获取数据集信息
export const getDatasetInfo = () => api.get('/dataset-info')

export default api