<template>
  <div class="dashboard">
    <header class="dash-header">
      <div class="header-left">
        <h1>数据看板</h1>
        <p class="header-sub">
          <template v-if="stats.datasource_name">
            {{ stats.datasource_name }}
            <span v-if="stats.profile_label" class="profile-tag">{{ stats.profile_label }}</span>
          </template>
          <template v-else>按数据源自适应生成指标与图表</template>
        </p>
      </div>
      <div class="header-right">
        <label class="ds-picker">
          <span class="ds-label">数据源</span>
          <select v-model="selectedDsId" :disabled="loading || dsLoading" @change="loadStats">
            <option v-for="ds in datasources" :key="ds.id" :value="ds.id">
              {{ ds.name }}{{ ds.is_default ? '（默认）' : '' }}
            </option>
          </select>
        </label>
        <button type="button" class="btn-refresh" :disabled="loading" @click="loadStats">
          {{ loading ? '加载中…' : '刷新' }}
        </button>
      </div>
    </header>

    <div v-if="error" class="banner warn">{{ error }}</div>
    <div v-else-if="stats.message && !loading" class="banner info">{{ stats.message }}</div>

    <div class="dash-content" v-if="!loading">
      <!-- KPI -->
      <section class="overview-cards" v-if="displayKpis.length">
        <div v-for="k in displayKpis" :key="k.key" class="stat-card">
          <div class="stat-icon" :class="k.icon || 'generic'">
            <span class="icon-letter">{{ (k.label || '?').slice(0, 1) }}</span>
          </div>
          <div class="stat-info">
            <span class="stat-label">{{ k.label }}</span>
            <span class="stat-value">{{ formatValue(k.value, k.format) }}</span>
          </div>
        </div>
      </section>
      <div v-else class="empty-hint">暂无 KPI（可能是空库，请先导入数据）</div>

      <!-- Charts -->
      <section class="charts-grid" v-if="displayCharts.length">
        <div
          v-for="ch in displayCharts"
          :key="ch.id"
          class="chart-card"
          :class="{ 'chart-wide': ch.wide || ch.type === 'bar' }"
        >
          <div class="chart-card-header">
            <h3>{{ ch.title }}</h3>
            <span class="chart-type">{{ typeLabel(ch.type) }}</span>
          </div>
          <div class="chart-card-body">
            <Bar
              v-if="ch.type === 'bar' && ch.labels?.length"
              :data="toChartData(ch)"
              :options="barChartOptions"
            />
            <Line
              v-else-if="ch.type === 'line' && ch.labels?.length"
              :data="toChartData(ch)"
              :options="lineChartOptions"
            />
            <Pie
              v-else-if="ch.type === 'pie' && ch.labels?.length"
              :data="toPieData(ch)"
              :options="pieChartOptions"
            />
            <div v-else class="no-data">暂无数据</div>
          </div>
        </div>
      </section>

      <!-- Tables summary -->
      <section class="tables-panel" v-if="stats.tables_summary?.length">
        <div class="panel-head">
          <h3>表概览</h3>
          <span class="muted">共 {{ stats.tables_summary.length }} 张表</span>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>表名</th>
                <th>列数</th>
                <th>行数</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="t in stats.tables_summary" :key="t.name">
                <td class="mono">{{ t.name }}</td>
                <td>{{ t.columns }}</td>
                <td>{{ formatNumber(t.rows) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>

    <div v-else class="loading-state">
      <div class="typing-dots"><span></span><span></span><span></span></div>
      <span>正在根据数据源结构生成看板…</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { Bar, Line, Pie } from 'vue-chartjs'
import {
  Chart as ChartJS,
  Title, Tooltip, Legend,
  BarElement, LineElement, PointElement,
  ArcElement, CategoryScale, LinearScale, Filler,
} from 'chart.js'
import { getDashboardOverview, listDatasources } from '../api'

ChartJS.register(
  Title, Tooltip, Legend,
  BarElement, LineElement, PointElement,
  ArcElement, CategoryScale, LinearScale, Filler,
)

const CHART_COLORS = [
  '#4f46e5', '#06b6d4', '#10b981', '#f59e0b', '#ef4444',
  '#8b5cf6', '#ec4899', '#14b8a6', '#f97316', '#6366f1',
]

const loading = ref(true)
const dsLoading = ref(true)
const error = ref('')
const datasources = ref([])
const selectedDsId = ref('')

const emptyStats = () => ({
  datasource_id: '',
  datasource_name: '',
  profile: '',
  profile_label: '',
  schema_ok: true,
  message: '',
  kpis: [],
  charts: [],
  tables_summary: [],
  total_revenue: 0,
  total_orders: 0,
  total_customers: 0,
  refund_rate: 0,
  category_revenue: { labels: [], data: [] },
  monthly_trend: { labels: [], data: [] },
  province_distribution: { labels: [], data: [] },
})

const stats = ref(emptyStats())

/** 优先用新结构 kpis；否则回退旧字段 */
const displayKpis = computed(() => {
  if (stats.value.kpis?.length) return stats.value.kpis
  // legacy fallback
  return [
    { key: 'revenue', label: '总销售额', value: stats.value.total_revenue, format: 'currency', icon: 'revenue' },
    { key: 'orders', label: '订单数', value: stats.value.total_orders, format: 'number', icon: 'orders' },
    { key: 'customers', label: '客户数', value: stats.value.total_customers, format: 'number', icon: 'customers' },
    { key: 'refund', label: '退款率', value: stats.value.refund_rate, format: 'percent', icon: 'refund' },
  ].filter((k) => k.value !== undefined && k.value !== null)
})

const displayCharts = computed(() => {
  if (stats.value.charts?.length) return stats.value.charts
  const out = []
  if (stats.value.category_revenue?.labels?.length) {
    out.push({
      id: 'legacy_cat',
      title: '分类排名',
      type: 'bar',
      labels: stats.value.category_revenue.labels,
      data: stats.value.category_revenue.data,
      dataset_label: '数值',
      wide: true,
    })
  }
  if (stats.value.monthly_trend?.labels?.length) {
    out.push({
      id: 'legacy_trend',
      title: '时间趋势',
      type: 'line',
      labels: stats.value.monthly_trend.labels,
      data: stats.value.monthly_trend.data,
      dataset_label: '数值',
    })
  }
  if (stats.value.province_distribution?.labels?.length) {
    out.push({
      id: 'legacy_pie',
      title: '分布',
      type: 'pie',
      labels: stats.value.province_distribution.labels,
      data: stats.value.province_distribution.data,
      dataset_label: '数值',
    })
  }
  return out
})

const barChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false } },
  scales: {
    x: { ticks: { font: { size: 11 }, maxRotation: 45, minRotation: 0 }, grid: { display: false } },
    y: { ticks: { font: { size: 11 } }, grid: { color: '#f1f5f9' } },
  },
}

const lineChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false } },
  scales: {
    x: { ticks: { font: { size: 11 } }, grid: { display: false } },
    y: { ticks: { font: { size: 11 } }, grid: { color: '#f1f5f9' } },
  },
}

const pieChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      position: 'bottom',
      labels: { font: { size: 11 }, padding: 12, usePointStyle: true },
    },
  },
}

function typeLabel(t) {
  return ({ bar: '柱状图', line: '折线图', pie: '饼图' })[t] || t
}

function toChartData(ch) {
  const n = ch.labels?.length || 0
  if (ch.type === 'line') {
    return {
      labels: ch.labels,
      datasets: [{
        label: ch.dataset_label || '数值',
        data: ch.data,
        borderColor: CHART_COLORS[0],
        backgroundColor: CHART_COLORS[0] + '22',
        fill: true,
        tension: 0.3,
        pointBackgroundColor: CHART_COLORS[0],
      }],
    }
  }
  return {
    labels: ch.labels,
    datasets: [{
      label: ch.dataset_label || '数值',
      data: ch.data,
      backgroundColor: CHART_COLORS.slice(0, Math.max(n, 1)),
      borderRadius: 6,
    }],
  }
}

function toPieData(ch) {
  const n = ch.labels?.length || 0
  return {
    labels: ch.labels,
    datasets: [{
      data: ch.data,
      backgroundColor: CHART_COLORS.slice(0, Math.max(n, 1)),
      borderWidth: 2,
      borderColor: '#fff',
    }],
  }
}

function formatNumber(val) {
  const num = Number(val) || 0
  return num.toLocaleString()
}

function formatCurrency(val) {
  if (!val) return '¥ 0'
  const num = Number(val)
  if (Math.abs(num) >= 10000) return '¥ ' + (num / 10000).toFixed(1) + '万'
  return '¥ ' + num.toLocaleString()
}

function formatValue(val, fmt) {
  if (fmt === 'currency') return formatCurrency(val)
  if (fmt === 'percent') return `${val ?? 0}%`
  if (fmt === 'text') return String(val ?? '-')
  return formatNumber(val)
}

async function loadDatasources() {
  dsLoading.value = true
  try {
    const { data } = await listDatasources()
    datasources.value = data.items || []
    if (!selectedDsId.value) {
      const def = datasources.value.find((d) => d.is_default) || datasources.value[0]
      selectedDsId.value = def?.id || ''
    }
  } catch {
    datasources.value = []
  } finally {
    dsLoading.value = false
  }
}

async function loadStats() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await getDashboardOverview(selectedDsId.value || null)
    stats.value = { ...emptyStats(), ...data }
    if (data.datasource_id) selectedDsId.value = data.datasource_id
  } catch (e) {
    error.value = e?.response?.data?.detail || e.message || '加载看板失败'
    stats.value = emptyStats()
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadDatasources()
  await loadStats()
})
</script>

<style scoped>
.dashboard {
  height: 100%;
  min-height: 0;
  overflow-y: auto;
  background: var(--bg);
  box-sizing: border-box;
}

.dash-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  padding: 18px 28px;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  z-index: 10;
}

.header-left h1 {
  font-size: 20px;
  font-weight: 800;
  margin: 0 0 4px;
  letter-spacing: -0.02em;
}

.header-sub {
  margin: 0;
  font-size: 12px;
  color: #64748b;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.profile-tag {
  display: inline-block;
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 999px;
  background: #eef2ff;
  color: #4338ca;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.ds-picker {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 6px 10px 6px 12px;
}

.ds-label {
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  white-space: nowrap;
}

.ds-picker select {
  border: none;
  background: transparent;
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
  outline: none;
  min-width: 160px;
  max-width: 280px;
  font-family: inherit;
}

.btn-refresh {
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #334155;
  border-radius: 10px;
  padding: 8px 14px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  font-family: inherit;
}

.btn-refresh:hover:not(:disabled) {
  border-color: #c7d2fe;
  color: #4338ca;
  background: #eef2ff;
}

.btn-refresh:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.banner {
  margin: 16px 28px 0;
  padding: 12px 14px;
  border-radius: 12px;
  font-size: 13px;
  line-height: 1.5;
}

.banner.warn {
  background: #fffbeb;
  border: 1px solid #fde68a;
  color: #92400e;
}

.banner.info {
  background: #eef2ff;
  border: 1px solid #c7d2fe;
  color: #3730a3;
}

.dash-content {
  width: 100%;
  margin: 0;
  padding: 20px 28px 28px;
  box-sizing: border-box;
}

.overview-cards {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 18px;
}

.stat-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  padding: 18px;
  display: flex;
  align-items: center;
  gap: 14px;
  box-shadow: 0 2px 10px rgba(15, 23, 42, 0.04);
  transition: transform 0.15s, box-shadow 0.15s;
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.08);
}

.stat-icon {
  width: 46px;
  height: 46px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-weight: 800;
  font-size: 16px;
}

.stat-icon.revenue { background: var(--primary-light); color: var(--primary); }
.stat-icon.orders { background: #ecfdf5; color: #10b981; }
.stat-icon.customers { background: #ecfeff; color: #0891b2; }
.stat-icon.refund { background: #fef2f2; color: #ef4444; }
.stat-icon.generic { background: #f1f5f9; color: #475569; }

.stat-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.stat-label {
  font-size: 12px;
  color: #64748b;
}

.stat-value {
  font-size: 22px;
  font-weight: 800;
  color: #0f172a;
  letter-spacing: -0.02em;
  word-break: break-all;
}

.charts-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  margin-bottom: 18px;
}

.chart-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 2px 10px rgba(15, 23, 42, 0.04);
}

.chart-card.chart-wide {
  grid-column: 1 / -1;
}

.chart-card-header {
  padding: 14px 18px;
  border-bottom: 1px solid #f1f5f9;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.chart-card-header h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 700;
}

.chart-type {
  font-size: 11px;
  color: #94a3b8;
  font-weight: 600;
}

.chart-card-body {
  padding: 16px 18px 18px;
  height: 300px;
  position: relative;
}

.no-data, .empty-hint {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #94a3b8;
  font-size: 13px;
  padding: 24px;
}

.tables-panel {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 2px 10px rgba(15, 23, 42, 0.04);
}

.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 18px;
  border-bottom: 1px solid #f1f5f9;
}

.panel-head h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 700;
}

.muted {
  font-size: 12px;
  color: #94a3b8;
}

.table-wrap {
  overflow: auto;
  max-height: 280px;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

th, td {
  padding: 10px 16px;
  text-align: left;
  border-bottom: 1px solid #f1f5f9;
}

th {
  background: #f8fafc;
  color: #64748b;
  font-weight: 700;
  position: sticky;
  top: 0;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  color: #334155;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 50vh;
  gap: 12px;
  color: #64748b;
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

@keyframes pulse {
  0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
  40% { opacity: 1; transform: scale(1); }
}

@media (max-width: 1100px) {
  .overview-cards {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .dash-header,
  .dash-content {
    padding-left: 16px;
    padding-right: 16px;
  }
  .overview-cards,
  .charts-grid {
    grid-template-columns: 1fr;
  }
  .chart-card.chart-wide {
    grid-column: auto;
  }
}
</style>
