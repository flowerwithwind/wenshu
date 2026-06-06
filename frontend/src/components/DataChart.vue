<template>
  <div class="data-chart" v-if="chartData">
    <div class="chart-header">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>
      </svg>
      <span>数据可视化</span>
      <div class="chart-type-selector">
        <button
          class="chart-type-btn"
          :class="{ active: chartType === 'bar' }"
          @click="chartType = 'bar'"
          title="柱状图"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="10" width="4" height="10"/><rect x="10" y="5" width="4" height="15"/><rect x="17" y="14" width="4" height="6"/>
          </svg>
        </button>
        <button
          class="chart-type-btn"
          :class="{ active: chartType === 'line' }"
          @click="chartType = 'line'"
          title="折线图"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3 17 9 10 13 14 21 6"/>
          </svg>
        </button>
        <button
          class="chart-type-btn"
          :class="{ active: chartType === 'pie' }"
          @click="chartType = 'pie'"
          title="饼图"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z"/><path d="M21 12h-9V3"/>
          </svg>
        </button>
      </div>
    </div>
    <div class="chart-container">
      <canvas ref="canvasRef"></canvas>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { Chart, registerables } from 'chart.js'

Chart.register(...registerables)

const props = defineProps({
  chartData: { type: Object, default: null },
})

const chartType = ref(props.chartData?.type || 'bar')
const canvasRef = ref(null)
let chartInstance = null

const COLORS = [
  '#4f46e5', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
  '#06b6d4', '#f97316', '#ec4899', '#84cc16', '#6366f1',
]

function renderChart() {
  if (!canvasRef.value || !props.chartData) return

  if (chartInstance) {
    chartInstance.destroy()
  }

  const ctx = canvasRef.value.getContext('2d')
  const data = props.chartData
  const datasets = (data.datasets || []).map((ds, i) => ({
    label: ds.label,
    data: ds.data,
    backgroundColor: chartType.value === 'pie'
      ? COLORS.slice(0, data.labels.length)
      : COLORS[i % COLORS.length] + '80',
    borderColor: COLORS[i % COLORS.length],
    borderWidth: 2,
    tension: 0.3,
  }))

  chartInstance = new Chart(ctx, {
    type: chartType.value === 'pie' ? 'pie' : chartType.value === 'line' ? 'line' : 'bar',
    data: { labels: data.labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      aspectRatio: 2,
      plugins: {
        legend: {
          position: 'bottom',
          labels: {
            font: { size: 12 },
            padding: 16,
            usePointStyle: true,
          },
        },
      },
      scales: chartType.value !== 'pie' ? {
        x: {
          ticks: { font: { size: 11 } },
          grid: { display: false },
        },
        y: {
          ticks: { font: { size: 11 } },
          grid: { color: '#f1f5f9' },
        },
      } : undefined,
    },
  })
}

watch(() => props.chartData, () => {
  chartType.value = props.chartData?.type || 'bar'
  nextTick(renderChart)
}, { deep: true })

watch(chartType, () => nextTick(renderChart))

onMounted(() => nextTick(renderChart))

onUnmounted(() => {
  if (chartInstance) {
    chartInstance.destroy()
  }
})
</script>

<style scoped>
.data-chart {
  margin-top: 16px;
  background: var(--bg);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  overflow: hidden;
}

.chart-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border);
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
}

.chart-type-selector {
  margin-left: auto;
  display: flex;
  gap: 4px;
}

.chart-type-btn {
  padding: 4px 6px;
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 4px;
  cursor: pointer;
  color: var(--text-secondary);
  transition: all var(--transition);
  display: flex;
  align-items: center;
}

.chart-type-btn:hover {
  border-color: var(--primary);
  color: var(--primary);
}

.chart-type-btn.active {
  background: var(--primary);
  border-color: var(--primary);
  color: #fff;
}

.chart-container {
  padding: 14px;
  max-height: 300px;
}
</style>