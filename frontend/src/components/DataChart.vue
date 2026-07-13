<template>
  <div class="data-chart" v-if="chartData">
    <div class="chart-header">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>
      </svg>
      <span>{{ chartData.title || '数据可视化' }}</span>
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
        <button
          class="chart-type-btn export-btn"
          @click="exportPNG"
          title="导出PNG"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
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
const chartRef = ref(null)
let chartInstance = null

const CHART_COLORS = [
  '#4f46e5', '#06b6d4', '#10b981', '#f59e0b', '#ef4444',
  '#8b5cf6', '#ec4899', '#14b8a6', '#f97316', '#6366f1',
]

const COLOR_SCHEMES = {
  indigo: ['#4f46e5', '#6366f1', '#818cf8', '#a5b4fc', '#c7d2fe'],
  ocean: ['#06b6d4', '#22d3ee', '#67e8f9', '#a5f3fc', '#cffafe'],
  forest: ['#10b981', '#34d399', '#6ee7b7', '#a7f3d0', '#d1fae5'],
  sunset: ['#f59e0b', '#fbbf24', '#fcd34d', '#fde68a', '#fef3c7'],
  rose: ['#ef4444', '#f87171', '#fca5a5', '#fecaca', '#fee2e2'],
  violet: ['#8b5cf6', '#a78bfa', '#c4b5fd', '#ddd6fe', '#ede9fe'],
}

function getColors() {
  const scheme = props.chartData?.colorScheme
  if (scheme && COLOR_SCHEMES[scheme]) {
    return COLOR_SCHEMES[scheme]
  }
  return CHART_COLORS
}

function renderChart() {
  if (!canvasRef.value || !props.chartData) return

  if (chartInstance) {
    chartInstance.destroy()
  }

  const ctx = canvasRef.value.getContext('2d')
  const data = props.chartData
  const colors = getColors()

  const datasets = (data.datasets || []).map((ds, i) => ({
    label: ds.label,
    data: ds.data,
    backgroundColor: chartType.value === 'pie'
      ? colors.slice(0, (data.labels || []).length)
      : colors[i % colors.length] + '80',
    borderColor: colors[i % colors.length],
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
        title: {
          display: !!data.title,
          text: data.title || '',
          font: { size: 14, weight: '600' },
          padding: { bottom: 16 },
        },
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

  chartRef.value = chartInstance
}

function exportPNG() {
  const chart = chartRef.value
  if (chart?.canvas) {
    const link = document.createElement('a')
    link.download = (props.chartData?.title || 'chart') + '.png'
    link.href = chart.canvas.toDataURL('image/png')
    link.click()
  }
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
  animation: fadeIn 0.5s ease-out 0.2s both;
}

@keyframes fadeIn {
  from { opacity: 0; transform: scale(0.95); }
  to { opacity: 1; transform: scale(1); }
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

.chart-type-btn.export-btn:hover {
  border-color: var(--success);
  color: var(--success);
}

.chart-container {
  padding: 14px;
  max-height: 300px;
}
</style>