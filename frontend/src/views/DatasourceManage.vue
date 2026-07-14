<template>
  <div class="page">
    <header class="page-header">
      <div class="header-text">
        <h1>数据源管理</h1>
        <p>统一管理 SQLite / MySQL / PostgreSQL 连接；智能问数与数据看板均可切换数据源</p>
      </div>
      <button class="btn primary" type="button" @click="openCreate">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
          <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
        </svg>
        新建数据源
      </button>
    </header>

    <div class="layout">
      <!-- 左侧：数据源列表 -->
      <section class="panel sources-panel">
        <div class="panel-head">
          <div>
            <h2>已配置数据源</h2>
            <span class="muted">共 {{ items.length }} 个</span>
          </div>
        </div>

        <div v-if="items.length" class="source-grid">
          <article
            v-for="ds in items"
            :key="ds.id"
            class="source-card"
            :class="{ default: ds.is_default, builtin: ds.is_builtin }"
          >
            <div class="source-top">
              <div class="type-badge" :data-type="ds.type">{{ typeLabel(ds.type) }}</div>
              <div class="badges">
                <span v-if="ds.is_default" class="pill on">默认</span>
                <span v-if="ds.is_builtin" class="pill muted">内置</span>
              </div>
            </div>

            <h3 class="source-name">{{ ds.name }}</h3>
            <p class="source-desc">{{ ds.description || '暂无描述' }}</p>

            <div class="source-meta">
              <template v-if="ds.type !== 'sqlite'">
                <div><span>主机</span>{{ ds.host || '-' }}:{{ ds.port || '-' }}</div>
                <div><span>库名</span>{{ ds.database || '-' }}</div>
                <div><span>用户</span>{{ ds.username || '-' }}</div>
              </template>
              <template v-else>
                <div><span>文件</span>内置 knowledge.db（电商演示）</div>
              </template>
            </div>

            <div class="source-actions">
              <button type="button" class="btn ghost" @click="test(ds)">测试连接</button>
              <button type="button" class="btn ghost" @click="openEdit(ds)">编辑</button>
              <button
                v-if="!ds.is_builtin"
                type="button"
                class="btn danger"
                @click="remove(ds)"
              >删除</button>
            </div>
          </article>
        </div>
        <div v-else class="empty-block">
          <div class="empty-title">还没有外部数据源</div>
          <p>点击右上角「新建数据源」连接 MySQL / PostgreSQL</p>
        </div>
      </section>

      <!-- 右侧：SQL 审计 -->
      <section class="panel audit-panel">
        <div class="panel-head">
          <div>
            <h2>SQL 审计日志</h2>
            <p class="panel-hint">
              记录智能问数 / Agent 实际执行的只读 SQL，便于排查权限与性能问题
            </p>
          </div>
          <button type="button" class="btn ghost" @click="loadAudit">刷新</button>
        </div>

        <div class="audit-table-wrap">
          <table v-if="audits.length" class="audit-table">
            <thead>
              <tr>
                <th>时间</th>
                <th>数据源</th>
                <th>来源</th>
                <th>SQL</th>
                <th>结果</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="a in audits" :key="a.id" :class="{ fail: !a.ok }">
                <td class="ts">{{ formatTs(a.ts) }}</td>
                <td>{{ a.datasource_name || '-' }}</td>
                <td><span class="src-tag">{{ a.source || '-' }}</span></td>
                <td class="sql" :title="a.sql">{{ a.sql }}</td>
                <td class="stat">
                  <span v-if="a.ok" class="ok">{{ a.row_count ?? 0 }} 行</span>
                  <span v-else class="err">{{ a.error || '失败' }}</span>
                </td>
              </tr>
            </tbody>
          </table>
          <div v-else class="empty-block compact">
            <div class="empty-title">暂无审计记录</div>
            <p>在智能问数中执行查询后，这里会显示最近执行的 SQL</p>
          </div>
        </div>
      </section>
    </div>

    <!-- 编辑弹窗 -->
    <div v-if="showForm" class="modal-mask" @click.self="showForm = false">
      <div class="modal">
        <header class="modal-head">
          <h3>{{ editingId ? '编辑数据源' : '新建数据源' }}</h3>
          <button type="button" class="icon-close" @click="showForm = false">×</button>
        </header>

        <div class="modal-body">
          <label class="field">名称
            <input v-model="form.name" placeholder="例如：生产订单库" />
          </label>
          <label class="field">类型
            <select v-model="form.type" :disabled="!!editingId && form.is_builtin">
              <option value="sqlite" disabled>SQLite（仅内置）</option>
              <option value="mysql">MySQL</option>
              <option value="postgres">PostgreSQL</option>
            </select>
          </label>
          <label class="field">描述
            <input v-model="form.description" placeholder="可选说明" />
          </label>
          <template v-if="form.type !== 'sqlite'">
            <div class="row2">
              <label class="field">Host<input v-model="form.host" placeholder="127.0.0.1" /></label>
              <label class="field">Port<input v-model.number="form.port" type="number" /></label>
            </div>
            <label class="field">Database<input v-model="form.database" /></label>
            <label class="field">Username<input v-model="form.username" /></label>
            <label class="field">Password
              <input
                v-model="form.password"
                type="password"
                :placeholder="editingId ? '留空则不修改' : '连接密码'"
              />
            </label>
          </template>
          <label class="check">
            <input type="checkbox" v-model="form.is_default" /> 设为默认数据源
          </label>
          <p v-if="formError" class="form-err">{{ formError }}</p>
        </div>

        <footer class="modal-actions">
          <button type="button" class="btn ghost" @click="testDraft">测试连接</button>
          <div class="spacer"></div>
          <button type="button" class="btn ghost" @click="showForm = false">取消</button>
          <button type="button" class="btn primary" @click="save">保存</button>
        </footer>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import {
  listDatasources,
  createDatasource,
  updateDatasource,
  deleteDatasource,
  testDatasource,
  getAuditLogs,
} from '../api'

const items = ref([])
const audits = ref([])
const showForm = ref(false)
const editingId = ref(null)
const formError = ref('')
const form = reactive({
  name: '',
  type: 'mysql',
  description: '',
  host: '127.0.0.1',
  port: 3306,
  database: '',
  username: '',
  password: '',
  is_default: false,
  is_builtin: false,
})

function typeLabel(t) {
  return ({ sqlite: 'SQLite', mysql: 'MySQL', postgres: 'PostgreSQL' })[t] || t
}

function formatTs(ts) {
  if (!ts) return '-'
  return String(ts).replace('T', ' ').slice(0, 19)
}

async function load() {
  const { data } = await listDatasources()
  items.value = data.items || []
}

async function loadAudit() {
  try {
    const { data } = await getAuditLogs({ limit: 80 })
    audits.value = data.items || []
  } catch {
    audits.value = []
  }
}

function openCreate() {
  editingId.value = null
  Object.assign(form, {
    name: '',
    type: 'mysql',
    description: '',
    host: '127.0.0.1',
    port: 3306,
    database: '',
    username: '',
    password: '',
    is_default: false,
    is_builtin: false,
  })
  formError.value = ''
  showForm.value = true
}

function openEdit(ds) {
  editingId.value = ds.id
  Object.assign(form, {
    name: ds.name,
    type: ds.type,
    description: ds.description || '',
    host: ds.host || '127.0.0.1',
    port: ds.port || (ds.type === 'postgres' ? 5432 : 3306),
    database: ds.database || '',
    username: ds.username || '',
    password: '',
    is_default: !!ds.is_default,
    is_builtin: !!ds.is_builtin,
  })
  formError.value = ''
  showForm.value = true
}

async function save() {
  formError.value = ''
  try {
    const payload = {
      name: form.name,
      type: form.type,
      description: form.description,
      host: form.host,
      port: form.port,
      database: form.database,
      username: form.username,
      password: form.password || undefined,
      is_default: form.is_default,
    }
    if (editingId.value) {
      await updateDatasource(editingId.value, payload)
    } else {
      if (form.type === 'sqlite') {
        formError.value = '请使用内置 SQLite，或选择 MySQL/PostgreSQL'
        return
      }
      await createDatasource(payload)
    }
    showForm.value = false
    await load()
  } catch (e) {
    formError.value = e?.response?.data?.detail || e.message || '保存失败'
  }
}

async function remove(ds) {
  if (!confirm(`确认删除数据源「${ds.name}」？`)) return
  try {
    await deleteDatasource(ds.id)
    await load()
  } catch (e) {
    alert(e?.response?.data?.detail || e.message)
  }
}

async function test(ds) {
  const { data } = await testDatasource({ id: ds.id })
  alert(data.ok ? `成功：${data.message} (${data.latency_ms}ms)` : `失败：${data.message}`)
}

async function testDraft() {
  const payload = editingId.value
    ? { id: editingId.value, password: form.password || undefined }
    : {
        type: form.type,
        host: form.host,
        port: form.port,
        database: form.database,
        username: form.username,
        password: form.password,
      }
  const { data } = await testDatasource(payload)
  alert(data.ok ? `成功：${data.message}` : `失败：${data.message}`)
}

onMounted(async () => {
  await load()
  await loadAudit()
})
</script>

<style scoped>
.page {
  height: 100%;
  min-height: 0;
  overflow-y: auto;
  padding: 20px 28px 28px;
  box-sizing: border-box;
  background:
    radial-gradient(ellipse 70% 40% at 0% 0%, rgba(79, 70, 229, 0.06), transparent),
    var(--bg);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 18px;
}

.header-text {
  min-width: 0;
  flex: 1;
}

.page-header h1 {
  font-size: 22px;
  font-weight: 800;
  margin: 0 0 6px;
  letter-spacing: -0.02em;
}

.page-header p {
  margin: 0;
  color: #64748b;
  font-size: 13px;
  line-height: 1.5;
  max-width: 640px;
}

.layout {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(320px, 0.85fr);
  gap: 16px;
  align-items: start;
}

.panel {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  box-shadow: 0 2px 12px rgba(15, 23, 42, 0.04);
  overflow: hidden;
}

.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  padding: 16px 18px;
  border-bottom: 1px solid #f1f5f9;
}

.panel-head h2 {
  margin: 0 0 4px;
  font-size: 15px;
  font-weight: 750;
}

.muted {
  font-size: 12px;
  color: #94a3b8;
}

.panel-hint {
  margin: 0;
  font-size: 12px;
  color: #64748b;
  line-height: 1.45;
  max-width: 360px;
}

.source-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 12px;
  padding: 16px 18px 18px;
}

.source-card {
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 14px;
  background: #f8fafc;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 190px;
  transition: border-color 0.15s, box-shadow 0.15s, transform 0.15s;
}

.source-card:hover {
  border-color: #c7d2fe;
  box-shadow: 0 8px 22px rgba(79, 70, 229, 0.08);
  transform: translateY(-1px);
}

.source-card.default {
  background: linear-gradient(180deg, #eef2ff, #f8fafc);
  border-color: #c7d2fe;
}

.source-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.type-badge {
  font-size: 11px;
  font-weight: 750;
  padding: 3px 8px;
  border-radius: 999px;
  background: #e2e8f0;
  color: #334155;
}

.type-badge[data-type="mysql"] { background: #ecfeff; color: #0e7490; }
.type-badge[data-type="postgres"] { background: #eff6ff; color: #1d4ed8; }
.type-badge[data-type="sqlite"] { background: #f1f5f9; color: #475569; }

.badges {
  display: flex;
  gap: 4px;
}

.pill {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 999px;
}

.pill.on { background: #e0e7ff; color: #4338ca; }
.pill.muted { background: #e2e8f0; color: #64748b; }

.source-name {
  margin: 0;
  font-size: 15px;
  font-weight: 750;
  color: #0f172a;
}

.source-desc {
  margin: 0;
  font-size: 12px;
  color: #64748b;
  line-height: 1.45;
  min-height: 34px;
}

.source-meta {
  margin-top: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 11px;
  color: #475569;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 8px 10px;
}

.source-meta span {
  color: #94a3b8;
  margin-right: 8px;
  font-family: inherit;
  font-weight: 600;
}

.source-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 4px;
}

.audit-panel {
  min-height: 420px;
  display: flex;
  flex-direction: column;
}

.audit-table-wrap {
  flex: 1;
  overflow: auto;
  max-height: calc(100vh - 220px);
}

.audit-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.audit-table th {
  position: sticky;
  top: 0;
  background: #f8fafc;
  text-align: left;
  padding: 10px 12px;
  color: #64748b;
  font-weight: 700;
  border-bottom: 1px solid #e2e8f0;
  white-space: nowrap;
}

.audit-table td {
  padding: 10px 12px;
  border-bottom: 1px solid #f1f5f9;
  color: #334155;
  vertical-align: top;
}

.audit-table tr.fail td {
  background: #fff7f7;
}

.audit-table .ts {
  white-space: nowrap;
  color: #64748b;
  font-variant-numeric: tabular-nums;
}

.audit-table .sql {
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11px;
}

.src-tag {
  display: inline-block;
  padding: 1px 7px;
  border-radius: 999px;
  background: #f1f5f9;
  color: #475569;
  font-size: 11px;
  font-weight: 600;
}

.stat .ok { color: #059669; font-weight: 650; }
.stat .err { color: #dc2626; font-weight: 650; }

.empty-block {
  padding: 48px 20px;
  text-align: center;
  color: #94a3b8;
}

.empty-block.compact {
  padding: 36px 16px;
}

.empty-title {
  font-size: 14px;
  font-weight: 700;
  color: #64748b;
  margin-bottom: 6px;
}

.empty-block p {
  margin: 0;
  font-size: 12px;
  line-height: 1.5;
}

.btn {
  border: none;
  border-radius: 10px;
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 650;
  cursor: pointer;
  font-family: inherit;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
}

.btn.primary {
  background: linear-gradient(135deg, #4f46e5, #6366f1);
  color: #fff;
  box-shadow: 0 6px 16px rgba(79, 70, 229, 0.28);
  padding: 10px 16px;
  flex-shrink: 0;
}

.btn.primary:hover {
  filter: brightness(1.05);
}

.btn.ghost {
  background: #fff;
  border: 1px solid #e2e8f0;
  color: #475569;
}

.btn.ghost:hover {
  border-color: #c7d2fe;
  color: #4338ca;
  background: #eef2ff;
}

.btn.danger {
  background: #fff;
  color: #dc2626;
  border: 1px solid #fecaca;
}

.btn.danger:hover {
  background: #fef2f2;
}

.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  padding: 20px;
}

.modal {
  width: min(520px, 100%);
  background: #fff;
  border-radius: 18px;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: 0 24px 64px rgba(15, 23, 42, 0.2);
}

.modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 18px;
  border-bottom: 1px solid #f1f5f9;
}

.modal-head h3 {
  margin: 0;
  font-size: 16px;
}

.icon-close {
  border: none;
  background: #f1f5f9;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 18px;
  color: #64748b;
  line-height: 1;
}

.modal-body {
  padding: 16px 18px;
  overflow: auto;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12px;
  font-weight: 650;
  color: #475569;
  margin-bottom: 10px;
}

.field input,
.field select {
  border: 1.5px solid #e2e8f0;
  border-radius: 10px;
  padding: 9px 11px;
  font-size: 13px;
  font-family: inherit;
  outline: none;
}

.field input:focus,
.field select:focus {
  border-color: #a5b4fc;
  box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.12);
}

.row2 {
  display: grid;
  grid-template-columns: 1fr 110px;
  gap: 10px;
}

.check {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  margin: 8px 0 4px;
  color: #334155;
}

.form-err {
  color: #dc2626;
  font-size: 12px;
  margin: 8px 0 0;
}

.modal-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 18px 16px;
  border-top: 1px solid #f1f5f9;
  background: #fafbfc;
}

.spacer { flex: 1; }

@media (max-width: 1100px) {
  .layout {
    grid-template-columns: 1fr;
  }
  .audit-table-wrap {
    max-height: 420px;
  }
}

@media (max-width: 640px) {
  .page {
    padding: 16px;
  }
  .page-header {
    flex-direction: column;
    align-items: stretch;
  }
  .btn.primary {
    width: 100%;
    justify-content: center;
  }
  .audit-table .sql {
    max-width: 140px;
  }
}
</style>
