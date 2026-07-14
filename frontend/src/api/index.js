import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
  headers: { 'Content-Type': 'application/json' },
})

// 健康检查
export const healthCheck = () => api.get('/health')

// 模型供应商
export const getModels = () => api.get('/models')
export const switchProvider = (provider) =>
  api.post('/models/provider', { provider })
export const saveModelConfig = (config) =>
  api.put('/models/config', config)

// 发送问题（非流式）
export const sendMessage = (question, conversationId = null) =>
  api.post('/chat', { question, conversation_id: conversationId })

// 流式发送问题（pipeline 或 agent）
export const sendMessageStream = (question, conversationId = null, mode = 'pipeline', datasourceId = null) => {
  const controller = new AbortController()
  const path = mode === 'agent' ? '/chat/agent/stream' : '/chat/stream'
  const response = fetch(`/api${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      question,
      conversation_id: conversationId,
      datasource_id: datasourceId || null,
    }),
    signal: controller.signal,
  })
  return { response, controller }
}

// 数据源管理
export const listDatasources = () => api.get('/datasources')
export const createDatasource = (data) => api.post('/datasources', data)
export const updateDatasource = (id, data) => api.put(`/datasources/${id}`, data)
export const deleteDatasource = (id) => api.delete(`/datasources/${id}`)
export const testDatasource = (data) => api.post('/datasources/test', data)
export const getAuditLogs = (params = {}) => api.get('/datasources/audit/logs', { params })

// Agent 非流式
export const sendAgentMessage = (question, conversationId = null) =>
  api.post('/chat/agent', { question, conversation_id: conversationId })

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

// 看板（可按数据源切换）
export const getDashboardOverview = (datasourceId = null) =>
  api.get('/dashboard/overview', {
    params: datasourceId ? { datasource_id: datasourceId } : {},
  })

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
