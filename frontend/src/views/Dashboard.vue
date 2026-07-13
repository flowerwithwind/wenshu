<template>
  <div class="dashboard">
    <header class="dash-header">
      <router-link to="/" class="back-link">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/>
        </svg>
        返回对话
      </router-link>
      <h1>数据看板</h1>
      <span class="update-time">数据实时更新</span>
    </header>

    <div class="dash-content" v-if="!loading">
      <!-- 概览卡片 -->
      <section class="overview-cards">
        <div class="stat-card">
          <div class="stat-icon revenue">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
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
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>
            </svg>
          </div>
          <div class="stat-info">
            <span class="stat-label">总订单数</span>
            <span class="stat-value">{{ stats.total_orders }}</span>
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-icon customers">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>
              <path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>
            </svg>
          </div>
          <div class="stat-info">
            <span class="stat-label">客户数</span>
            <span class="stat-value">{{ stats.total_customers }}</span>
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-icon refund">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
            </svg>
          </div>
          <div class="stat-info">
            <span class="stat-label">退款率</span>
            <span class="stat-value">{{ stats.refund_rate }}%</span>
          </div>
        </div>
      </section>

      <!-- 图表区域 -->
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
      <span>加载看板数据...</span>
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
import api from '../api'

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
const stats = ref({
  total_revenue: 0,
  total_orders: 0,
  total_customers: 0,
  refund_rate: 0,
  category_revenue: { labels: [], data: [] },
  monthly_trend: { labels: [], data: [] },
  province_distribution: { labels: [], data: [] },
})

const categoryChartData = computed(() => ({
  labels: stats.value.category_revenue.labels,
  datasets: [{
    label: '销售额 (元)',
    data: stats.value.category_revenue.data,
    backgroundColor: CHART_COLORS.slice(0, stats.value.category_revenue.labels.length),
    borderRadius: 6,
  }],
}))

const monthlyTrendData = computed(() => ({
  labels: stats.value.monthly_trend.labels,
  datasets: [{
    label: '销售额 (元)',
    data: stats.value.monthly_trend.data,
    borderColor: CHART_COLORS[0],
    backgroundColor: CHART_COLORS[0] + '20',
    fill: true,
    tension: 0.3,
    pointBackgroundColor: CHART_COLORS[0],
  }],
}))

const provincePieData = computed(() => ({
  labels: stats.value.province_distribution.labels,
  datasets: [{
    data: stats.value.province_distribution.data,
    backgroundColor: CHART_COLORS.slice(0, stats.value.province_distribution.labels.length),
    borderWidth: 2,
    borderColor: '#fff',
  }],
}))

const barChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: false },
  },
  scales: {
    x: { ticks: { font: { size: 11 } }, grid: { display: false } },
    y: { ticks: { font: { size: 11 } }, grid: { color: '#f1f5f9' } },
  },
}

const lineChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: false },
  },
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
  if (num >= 10000) {
    return '¥ ' + (num / 10000).toFixed(1) + '万'
  }
  return '¥ ' + num.toLocaleString()
}

onMounted(async () => {
  try {
    const { data } = await api.get('/dashboard/overview')
    stats.value = data
  } catch (e) {
    console.error('Failed to load dashboard:', e)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.dashboard {
  min-height: 100vh;
  background: var(--bg);
}

.dash-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 24px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  z-index: 10;
}

.back-link {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 14px;
  transition: color var(--transition);
}

.back-link:hover {
  color: var(--primary);
}

.dash-header h1 {
  font-size: 20px;
  font-weight: 700;
  flex: 1;
}

.update-time {
  font-size: 12px;
  color: var(--text-secondary);
}

.dash-content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}

/* 概览卡片 */
.overview-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.stat-card {
  background: var(--bg-card);
  border-radius: var(--radius);
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  box-shadow: var(--shadow);
  transition: transform var(--transition), box-shadow var(--transition);
  animation: fadeIn 0.5s ease-out both;
}

.stat-card:nth-child(1) { animation-delay: 0.1s; }
.stat-card:nth-child(2) { animation-delay: 0.2s; }
.stat-card:nth-child(3) { animation-delay: 0.3s; }
.stat-card:nth-child(4) { animation-delay: 0.4s; }

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-lg);
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stat-icon.revenue { background: #eef2ff; color: #4f46e5; }
.stat-icon.orders { background: #ecfdf5; color: #10b981; }
.stat-icon.customers { background: #eff6ff; color: #06b6d4; }
.stat-icon.refund { background: #fef2f2; color: #ef4444; }

.stat-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-label {
  font-size: 13px;
  color: var(--text-secondary);
}

.stat-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--text);
}

/* 图表区域 */
.charts-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.chart-card {
  background: var(--bg-card);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  overflow: hidden;
  animation: fadeIn 0.5s ease-out 0.2s both;
}

.chart-card.chart-wide {
  grid-column: 1 / -1;
}

.chart-card-header {
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
}

.chart-card-header h3 {
  font-size: 15px;
  font-weight: 600;
}

.chart-card-body {
  padding: 20px;
  height: 320px;
  position: relative;
}

.no-data {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-secondary);
  font-size: 14px;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 60vh;
  gap: 12px;
  color: var(--text-secondary);
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

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}

@media (max-width: 768px) {
  .overview-cards {
    grid-template-columns: repeat(2, 1fr);
  }
  .charts-grid {
    grid-template-columns: 1fr;
  }
  .dash-content {
    padding: 16px;
  }
}
</style>