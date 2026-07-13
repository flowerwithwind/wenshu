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

// 上传文件
export const uploadFile = (file, tableName = null, config = {}) => {
  const formData = new FormData()
  formData.append('file', file)
  if (tableName) formData.append('table_name', tableName)
  return api.post('/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
    ...config,
  })
}

// 知识库管理
export const getKnowledge = () => api.get('/knowledge')
export const getKnowledgeStats = () => api.get('/knowledge/stats')
export const createExample = (data) => api.post('/knowledge/examples', data)
export const deleteExample = (index) => api.delete(`/knowledge/examples/${index}`)
export const createSynonym = (data) => api.post('/knowledge/synonyms', data)
export const deleteSynonym = (index) => api.delete(`/knowledge/synonyms/${index}`)
export const createDomainMapping = (data) => api.post('/knowledge/domain-mappings', data)
export const deleteDomainMapping = (index) => api.delete(`/knowledge/domain-mappings/${index}`)

export default api