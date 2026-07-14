<template>
  <div class="page">
    <header class="page-header">
      <div class="header-text">
        <h1>数据源管理</h1>
        <p>
          先<strong>创建数据源</strong>（连接/空库），再<strong>导入 CSV/Excel 表</strong>；
          支持 SQLite / MySQL / PostgreSQL。智能问数与看板可切换数据源。
        </p>
      </div>
      <button class="btn primary" type="button" @click="openCreate">+ 新建数据源</button>
    </header>

    <div v-if="banner" class="banner" :class="banner.type">
      {{ banner.text }}
      <button v-if="banner.importId" type="button" class="btn ghost sm" @click="openImport({ id: banner.importId, name: banner.name })">
        立即导入数据
      </button>
      <button type="button" class="btn-x" @click="banner = null">×</button>
    </div>

    <div class="layout">
      <section class="panel sources-panel">
        <div class="panel-head">
          <div>
            <h2>已配置数据源</h2>
            <span class="muted">共 {{ items.length }} 个 · 创建 ≠ 已有业务数据</span>
          </div>
        </div>

        <div v-if="items.length" class="source-grid">
          <article
            v-for="ds in items"
            :key="ds.id"
            class="source-card"
            :class="{ default: ds.is_default, empty: ds.needs_import }"
          >
            <div class="source-top">
              <div class="type-badge" :data-type="ds.type">{{ typeLabel(ds.type) }}</div>
              <div class="badges">
                <span v-if="ds.is_default" class="pill on">默认</span>
                <span v-if="ds.is_builtin" class="pill muted">内置</span>
                <span v-if="ds.needs_import" class="pill warn">待导入</span>
                <span v-else-if="ds.table_count != null" class="pill ok">{{ ds.table_count }} 表</span>
              </div>
            </div>

            <h3 class="source-name">{{ ds.name }}</h3>
            <p class="source-desc">{{ ds.description || '暂无描述' }}</p>

            <div class="source-meta">
              <template v-if="ds.type === 'sqlite'">
                <div><span>文件</span>{{ ds.database || ds.db_path || 'SQLite' }}</div>
              </template>
              <template v-else>
                <div><span>主机</span>{{ ds.host || '-' }}:{{ ds.port || '-' }}</div>
                <div><span>库名</span>{{ ds.database || '-' }}</div>
                <div><span>用户</span>{{ ds.username || '-' }}</div>
              </template>
            </div>

            <p v-if="ds.needs_import" class="hint-import">
              已创建连接，但还没有业务表。请点击「导入数据」上传 CSV/Excel。
            </p>

            <div class="source-actions">
              <button type="button" class="btn ghost" @click="test(ds)">测试</button>
              <button
                v-if="!ds.is_builtin"
                type="button"
                class="btn primary sm"
                @click="openImport(ds)"
              >导入数据</button>
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
          <div class="empty-title">还没有数据源</div>
          <p>点击右上角新建 SQLite / MySQL / PostgreSQL</p>
        </div>
      </section>

      <section class="panel audit-panel">
        <div class="panel-head">
          <div>
            <h2>SQL 审计日志</h2>
            <p class="panel-hint">记录智能问数实际执行的只读 SQL</p>
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
          </div>
        </div>
      </section>
    </div>

    <!-- 新建/编辑 -->
    <div v-if="showForm" class="modal-mask" @click.self="showForm = false">
      <div class="modal">
        <header class="modal-head">
          <h3>{{ editingId ? '编辑数据源' : '新建数据源' }}</h3>
          <button type="button" class="icon-close" @click="showForm = false">×</button>
        </header>
        <div class="modal-body">
          <p class="form-tip">
            创建阶段只保存连接信息；SQLite 会生成空库文件。业务表请在创建后「导入数据」。
          </p>
          <label class="field">名称
            <input v-model="form.name" placeholder="例如：医院分析库" />
          </label>
          <label class="field">类型
            <select v-model="form.type" :disabled="!!editingId && form.is_builtin" @change="onTypeChange">
              <option value="sqlite">SQLite（本地文件库）</option>
              <option value="mysql">MySQL</option>
              <option value="postgres">PostgreSQL</option>
            </select>
          </label>
          <label class="field">描述
            <input v-model="form.description" placeholder="可选说明" />
          </label>
          <template v-if="form.type === 'sqlite'">
            <label class="field">库文件名（可选）
              <input v-model="form.database" placeholder="留空则自动生成 xxx.db" :disabled="!!editingId" />
            </label>
          </template>
          <template v-else>
            <div class="row2">
              <label class="field">Host<input v-model="form.host" placeholder="127.0.0.1" /></label>
              <label class="field">Port<input v-model.number="form.port" type="number" /></label>
            </div>
            <label class="field">Database<input v-model="form.database" placeholder="已存在的库名" /></label>
            <label class="field">Username<input v-model="form.username" /></label>
            <label class="field">Password
              <input v-model="form.password" type="password" :placeholder="editingId ? '留空则不修改' : ''" />
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

    <!-- 导入 -->
    <div v-if="showImport" class="modal-mask" @click.self="showImport = false">
      <div class="modal">
        <header class="modal-head">
          <h3>导入数据 · {{ importTarget?.name }}</h3>
          <button type="button" class="icon-close" @click="showImport = false">×</button>
        </header>
        <div class="modal-body">
          <p class="form-tip">支持 CSV / Excel。可多次导入多张表。表名默认取文件名。</p>
          <label class="field">表名（可选）
            <input v-model="importTableName" placeholder="例如 patients" />
          </label>
          <label class="field">选择文件
            <input type="file" accept=".csv,.xlsx,.xls" @change="onFilePick" />
          </label>
          <label class="check">
            <input type="checkbox" v-model="importUseLlm" />
            导入后用当前模型 AI 增强知识库（可选，更慢）
          </label>
          <p class="form-tip" style="margin-top:8px">
            导入成功后会<strong>自动规则生成</strong>该数据源的 Few-shot / 同义词；也可稍后在知识库页「扫描生成」。
          </p>
          <p v-if="importMsg" class="form-ok">{{ importMsg }}</p>
          <p v-if="importErr" class="form-err">{{ importErr }}</p>
          <div v-if="importTables.length" class="tables-list">
            当前表：{{ importTables.join(', ') }}
          </div>
          <div class="source-actions" style="margin-top:10px" v-if="importTarget">
            <button type="button" class="btn ghost" :disabled="bootstrapping" @click="doBootstrap(false)">
              {{ bootstrapping ? '生成中…' : '仅扫描生成知识库' }}
            </button>
            <button type="button" class="btn ghost" :disabled="bootstrapping" @click="doBootstrap(true)">
              AI 增强知识库
            </button>
          </div>
        </div>
        <footer class="modal-actions">
          <button type="button" class="btn ghost" @click="showImport = false">关闭</button>
          <button type="button" class="btn primary" :disabled="!importFile || importing" @click="doImport">
            {{ importing ? '导入中…' : '开始导入' }}
          </button>
        </footer>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import ToastNotification from '../components/ToastNotification.vue'
import {
  listDatasources,
  createDatasource,
  updateDatasource,
  deleteDatasource,
  testDatasource,
  getAuditLogs,
  importToDatasource,
  bootstrapKnowledge,
} from '../api'

const items = ref([])
const audits = ref([])
const showForm = ref(false)
const editingId = ref(null)
const formError = ref('')
const banner = ref(null)

const showImport = ref(false)
const importTarget = ref(null)
const importFile = ref(null)
const importTableName = ref('')
const importMsg = ref('')
const importErr = ref('')
const importTables = ref([])
const importing = ref(false)
const importUseLlm = ref(false)
const bootstrapping = ref(false)

const form = reactive({
  name: '',
  type: 'sqlite',
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

function onTypeChange() {
  if (form.type === 'postgres') form.port = 5432
  else if (form.type === 'mysql') form.port = 3306
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
    type: 'sqlite',
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

function openImport(ds) {
  importTarget.value = ds
  importFile.value = null
  importTableName.value = ''
  importMsg.value = ''
  importErr.value = ''
  importTables.value = []
  importUseLlm.value = false
  showImport.value = true
  banner.value = null
}

function onFilePick(e) {
  importFile.value = e.target.files?.[0] || null
}

async function doImport() {
  if (!importFile.value || !importTarget.value) return
  importing.value = true
  importErr.value = ''
  importMsg.value = ''
  try {
    const { data } = await importToDatasource(
      importTarget.value.id,
      importFile.value,
      importTableName.value || null,
      importUseLlm.value,
    )
    importMsg.value = data.message || '导入成功'
    importTables.value = data.tables || []
    if (data.knowledge?.message) {
      importMsg.value += `（${data.knowledge.message}）`
    }
    await load()
  } catch (e) {
    importErr.value = e?.response?.data?.detail || e.message || '导入失败'
  } finally {
    importing.value = false
  }
}

async function doBootstrap(useLlm) {
  if (!importTarget.value) return
  bootstrapping.value = true
  importErr.value = ''
  try {
    const { data } = await bootstrapKnowledge(importTarget.value.id, {
      useLlm,
      merge: true,
    })
    importMsg.value = data.message || '知识库已更新'
  } catch (e) {
    importErr.value = e?.response?.data?.detail || e.message || '知识库生成失败'
  } finally {
    bootstrapping.value = false
  }
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
    let data
    if (editingId.value) {
      ;({ data } = await updateDatasource(editingId.value, payload))
      showForm.value = false
    } else {
      ;({ data } = await createDatasource(payload))
      showForm.value = false
      banner.value = {
        type: 'info',
        text: data.next_step || '数据源已创建。请导入业务数据表。',
        importId: data.id,
        name: data.name,
      }
    }
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
  const extra = data.table_count != null ? `，${data.table_count} 张表` : ''
  alert(data.ok ? `成功：${data.message}${extra}` : `失败：${data.message}`)
  await load()
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
  height: 100%; min-height: 0; overflow-y: auto; padding: 20px 28px 28px;
  box-sizing: border-box;
  background: radial-gradient(ellipse 70% 40% at 0% 0%, rgba(79,70,229,0.06), transparent), var(--bg);
}
.page-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 16px; }
.header-text { flex: 1; min-width: 0; }
.page-header h1 { font-size: 22px; font-weight: 800; margin: 0 0 6px; }
.page-header p { margin: 0; color: #64748b; font-size: 13px; line-height: 1.5; max-width: 720px; }
.banner {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  padding: 12px 14px; border-radius: 12px; margin-bottom: 14px; font-size: 13px;
}
.banner.info { background: #eef2ff; border: 1px solid #c7d2fe; color: #3730a3; }
.btn-x { border: none; background: transparent; cursor: pointer; font-size: 18px; margin-left: auto; }
.layout { display: grid; grid-template-columns: minmax(0,1.15fr) minmax(320px,0.85fr); gap: 16px; align-items: start; }
.panel { background: #fff; border: 1px solid #e2e8f0; border-radius: 16px; box-shadow: 0 2px 12px rgba(15,23,42,0.04); overflow: hidden; }
.panel-head { display: flex; justify-content: space-between; gap: 12px; padding: 16px 18px; border-bottom: 1px solid #f1f5f9; }
.panel-head h2 { margin: 0 0 4px; font-size: 15px; font-weight: 750; }
.muted { font-size: 12px; color: #94a3b8; }
.panel-hint { margin: 0; font-size: 12px; color: #64748b; }
.source-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 12px; padding: 16px 18px 18px; }
.source-card {
  border: 1px solid #e2e8f0; border-radius: 14px; padding: 14px; background: #f8fafc;
  display: flex; flex-direction: column; gap: 8px; min-height: 200px;
}
.source-card.default { background: linear-gradient(180deg, #eef2ff, #f8fafc); border-color: #c7d2fe; }
.source-card.empty { border-color: #fde68a; background: #fffbeb; }
.source-top { display: flex; justify-content: space-between; gap: 8px; align-items: center; }
.type-badge { font-size: 11px; font-weight: 750; padding: 3px 8px; border-radius: 999px; background: #e2e8f0; color: #334155; }
.type-badge[data-type="mysql"] { background: #ecfeff; color: #0e7490; }
.type-badge[data-type="postgres"] { background: #eff6ff; color: #1d4ed8; }
.type-badge[data-type="sqlite"] { background: #f1f5f9; color: #475569; }
.badges { display: flex; gap: 4px; flex-wrap: wrap; }
.pill { font-size: 10px; font-weight: 700; padding: 2px 7px; border-radius: 999px; }
.pill.on { background: #e0e7ff; color: #4338ca; }
.pill.muted { background: #e2e8f0; color: #64748b; }
.pill.warn { background: #fef3c7; color: #b45309; }
.pill.ok { background: #d1fae5; color: #047857; }
.source-name { margin: 0; font-size: 15px; font-weight: 750; }
.source-desc { margin: 0; font-size: 12px; color: #64748b; min-height: 32px; }
.source-meta {
  margin-top: auto; display: flex; flex-direction: column; gap: 4px; font-size: 11px; color: #475569;
  font-family: ui-monospace, monospace; background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 8px 10px;
}
.source-meta span { color: #94a3b8; margin-right: 8px; font-weight: 600; font-family: inherit; }
.hint-import { margin: 0; font-size: 12px; color: #b45309; line-height: 1.4; }
.source-actions { display: flex; flex-wrap: wrap; gap: 6px; }
.audit-panel { min-height: 420px; display: flex; flex-direction: column; }
.audit-table-wrap { flex: 1; overflow: auto; max-height: calc(100vh - 220px); }
.audit-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.audit-table th { position: sticky; top: 0; background: #f8fafc; text-align: left; padding: 10px 12px; color: #64748b; border-bottom: 1px solid #e2e8f0; }
.audit-table td { padding: 10px 12px; border-bottom: 1px solid #f1f5f9; vertical-align: top; }
.audit-table tr.fail td { background: #fff7f7; }
.audit-table .sql { max-width: 240px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-family: ui-monospace, monospace; font-size: 11px; }
.src-tag { display: inline-block; padding: 1px 7px; border-radius: 999px; background: #f1f5f9; font-size: 11px; font-weight: 600; }
.stat .ok { color: #059669; font-weight: 650; }
.stat .err { color: #dc2626; font-weight: 650; }
.empty-block { padding: 40px 20px; text-align: center; color: #94a3b8; }
.empty-block.compact { padding: 28px 16px; }
.empty-title { font-size: 14px; font-weight: 700; color: #64748b; margin-bottom: 6px; }
.btn { border: none; border-radius: 10px; padding: 8px 12px; font-size: 12px; font-weight: 650; cursor: pointer; font-family: inherit; display: inline-flex; align-items: center; gap: 6px; }
.btn.primary { background: linear-gradient(135deg, #4f46e5, #6366f1); color: #fff; }
.btn.primary.sm, .btn.ghost.sm { padding: 6px 10px; font-size: 11px; }
.btn.ghost { background: #fff; border: 1px solid #e2e8f0; color: #475569; }
.btn.danger { background: #fff; color: #dc2626; border: 1px solid #fecaca; }
.modal-mask { position: fixed; inset: 0; background: rgba(15,23,42,0.45); display: flex; align-items: center; justify-content: center; z-index: 100; padding: 20px; }
.modal { width: min(520px, 100%); background: #fff; border-radius: 18px; max-height: 90vh; overflow: hidden; display: flex; flex-direction: column; box-shadow: 0 24px 64px rgba(15,23,42,0.2); }
.modal-head { display: flex; align-items: center; justify-content: space-between; padding: 16px 18px; border-bottom: 1px solid #f1f5f9; }
.modal-head h3 { margin: 0; font-size: 16px; }
.icon-close { border: none; background: #f1f5f9; width: 28px; height: 28px; border-radius: 8px; cursor: pointer; font-size: 18px; }
.modal-body { padding: 16px 18px; overflow: auto; }
.form-tip { margin: 0 0 12px; font-size: 12px; color: #64748b; line-height: 1.5; background: #f8fafc; border-radius: 10px; padding: 10px 12px; }
.field { display: flex; flex-direction: column; gap: 6px; font-size: 12px; font-weight: 650; color: #475569; margin-bottom: 10px; }
.field input, .field select { border: 1.5px solid #e2e8f0; border-radius: 10px; padding: 9px 11px; font-size: 13px; font-family: inherit; }
.row2 { display: grid; grid-template-columns: 1fr 110px; gap: 10px; }
.check { display: flex; align-items: center; gap: 8px; font-size: 13px; margin: 8px 0 4px; }
.form-err { color: #dc2626; font-size: 12px; }
.form-ok { color: #059669; font-size: 12px; }
.tables-list { margin-top: 10px; font-size: 12px; color: #475569; line-height: 1.5; }
.modal-actions { display: flex; align-items: center; gap: 8px; padding: 12px 18px 16px; border-top: 1px solid #f1f5f9; background: #fafbfc; }
.spacer { flex: 1; }
@media (max-width: 1100px) { .layout { grid-template-columns: 1fr; } }
</style>
.modal-body { padding: 16px 18px; overflow: auto; }
.form-tip { margin: 0 0 12px; font-size: 12px; color: #64748b; line-height: 1.5; background: #f8fafc; border-radius: 10px; padding: 10px 12px; }
.field { display: flex; flex-direction: column; gap: 6px; font-size: 12px; font-weight: 650; color: #475569; margin-bottom: 10px; }
.field input, .field select { border: 1.5px solid #e2e8f0; border-radius: 10px; padding: 9px 11px; font-size: 13px; font-family: inherit; }
.row2 { display: grid; grid-template-columns: 1fr 110px; gap: 10px; }
.check { display: flex; align-items: center; gap: 8px; font-size: 13px; margin: 8px 0 4px; }
.form-err { color: #dc2626; font-size: 12px; }
.form-ok { color: #059669; font-size: 12px; }
.tables-list { margin-top: 10px; font-size: 12px; color: #475569; line-height: 1.5; }
.modal-actions { display: flex; align-items: center; gap: 8px; padding: 12px 18px 16px; border-top: 1px solid #f1f5f9; background: #fafbfc; }
.spacer { flex: 1; }
@media (max-width: 1100px) { .layout { grid-template-columns: 1fr; } }
</style>
.modal-body { padding: 16px 18px; overflow: auto; }
.form-tip { margin: 0 0 12px; font-size: 12px; color: #64748b; line-height: 1.5; background: #f8fafc; border-radius: 10px; padding: 10px 12px; }
.field { display: flex; flex-direction: column; gap: 6px; font-size: 12px; font-weight: 650; color: #475569; margin-bottom: 10px; }
.field input, .field select { border: 1.5px solid #e2e8f0; border-radius: 10px; padding: 9px 11px; font-size: 13px; font-family: inherit; }
.row2 { display: grid; grid-template-columns: 1fr 110px; gap: 10px; }
.check { display: flex; align-items: center; gap: 8px; font-size: 13px; margin: 8px 0 4px; }
.form-err { color: #dc2626; font-size: 12px; }
.form-ok { color: #059669; font-size: 12px; }
.tables-list { margin-top: 10px; font-size: 12px; color: #475569; line-height: 1.5; }
.modal-actions { display: flex; align-items: center; gap: 8px; padding: 12px 18px 16px; border-top: 1px solid #f1f5f9; background: #fafbfc; }
.spacer { flex: 1; }
@media (max-width: 1100px) { .layout { grid-template-columns: 1fr; } }
</style>
