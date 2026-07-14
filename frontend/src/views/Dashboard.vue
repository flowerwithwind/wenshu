<template>
  <div class="dashboard">
    <header class="dash-header">
      <div class="header-left">
        <h1>数据看板</h1>
        <p class="header-sub">
          {{ stats.datasource_name ? `数据源：${stats.datasource_name}` : '电商核心指标概览' }}
        </p>
      </div>
      <div class="header-right">
        <label class="ds-picker">
          <span class="ds-label">数据源</span>
          <select
            v-model="selectedDsId"
            :disabled="loading || dsLoading"
            @change="loadStats"
          >
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
    <div v-else-if="stats.message && !stats.schema_ok && !loading" class="banner warn">
      {{ stats.message }}
    </div>

    <div class="dash-content" v-if="!loading">
      <section class="overview-cards">
        <div class="stat-card">
          <div class="stat-icon revenue">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>
            </svg>
          </div>
          <div class="stat-info">
            <span class="stat-label">总销售额</span>
            <span class="stat-value">{{ formatCurrency(stats.total_revenue) }}</span>
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-icon orders">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
            </svg>
          </div>
          <div class="stat-info">
            <span class="stat-label">总订单数</span>
            <span class="stat-value">{{ stats.total_orders ?? 0 }}</span>
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-icon customers">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>
              <path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>
            </svg>
          </div>
          <div class="stat-info">
            <span class="stat-label">客户数</span>
            <span class="stat-value">{{ stats.total_customers ?? 0 }}</span>
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-icon refund">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
            </svg>
          </div>
          <div class="stat-info">
            <span class="stat-label">退款率</span>
            <span class="stat-value">{{ stats.refund_rate ?? 0 }}%</span>
          </div>
        </div>
      </section>

      <section class="charts-grid">
        <div class="chart-card chart-wide">
          <div class="chart-card-header">
            <h3>各品类销售额排名</h3>
          </div>
          <div class="chart-card-body">
            <Bar
              v-if="stats.category_revenue?.labels?.length"
              :data="categoryChartData"
              :options="barChartOptions"
            />
            <div v-else class="no-data">暂无数据</div>
          </div>
        </div>

        <div class="chart-card">
          <div class="chart-card-header">
            <h3>月度销售趋势</h3>
          </div>
          <div class="chart-card-body">
            <Line
              v-if="stats.monthly_trend?.labels?.length"
              :data="monthlyTrendData"
              :options="lineChartOptions"
            />
            <div v-else class="no-data">暂无数据</div>
          </div>
        </div>

        <div class="chart-card">
          <div class="chart-card-header">
            <h3>省份销售分布</h3>
          </div>
          <div class="chart-card-body">
            <Pie
              v-if="stats.province_distribution?.labels?.length"
              :data="provincePieData"
              :options="pieChartOptions"
            />
            <div v-else class="no-data">暂无数据</div>
          </div>
        </div>
      </section>
    </div>

    <div v-else class="loading-state">
      <div class="typing-dots"><span></span><span></span><span></span></div>
      <span>加载看板数据…</span>
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
  total_revenue: 0,
  total_orders: 0,
  total_customers: 0,
  refund_rate: 0,
  category_revenue: { labels: [], data: [] },
  monthly_trend: { labels: [], data: [] },
  province_distribution: { labels: [], data: [] },
  schema_ok: true,
  message: '',
})

const stats = ref(emptyStats())

const categoryChartData = computed(() => ({
  labels: stats.value.category_revenue?.labels || [],
  datasets: [{
    label: '销售额 (元)',
    data: stats.value.category_revenue?.data || [],
    backgroundColor: CHART_COLORS.slice(0, (stats.value.category_revenue?.labels || []).length),
    borderRadius: 6,
  }],
}))

const monthlyTrendData = computed(() => ({
  labels: stats.value.monthly_trend?.labels || [],
  datasets: [{
    label: '销售额 (元)',
    data: stats.value.monthly_trend?.data || [],
    borderColor: CHART_COLORS[0],
    backgroundColor: CHART_COLORS[0] + '20',
    fill: true,
    tension: 0.3,
    pointBackgroundColor: CHART_COLORS[0],
  }],
}))

const provincePieData = computed(() => ({
  labels: stats.value.province_distribution?.labels || [],
  datasets: [{
    data: stats.value.province_distribution?.data || [],
    backgroundColor: CHART_COLORS.slice(0, (stats.value.province_distribution?.labels || []).length),
    borderWidth: 2,
    borderColor: '#fff',
  }],
}))

const barChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false } },
  scales: {
    x: { ticks: { font: { size: 11 } }, grid: { display: false } },
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

function formatCurrency(val) {
  if (!val) return '¥ 0'
  const num = Number(val)
  if (num >= 10000) return '¥ ' + (num / 10000).toFixed(1) + '万'
  return '¥ ' + num.toLocaleString()
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
  max-width: 260px;
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

.dash-content {
  width: 100%;
  max-width: none;
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
}

.stat-icon.revenue { background: #eef2ff; color: #4f46e5; }
.stat-icon.orders { background: #ecfdf5; color: #10b981; }
.stat-icon.customers { background: #ecfeff; color: #0891b2; }
.stat-icon.refund { background: #fef2f2; color: #ef4444; }

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
}

.charts-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
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
}

.chart-card-header h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 700;
}

.chart-card-body {
  padding: 16px 18px 18px;
  height: 320px;
  position: relative;
}

.no-data {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #94a3b8;
  font-size: 13px;
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
  .ds-picker select {
    min-width: 120px;
  }
}
</style>
