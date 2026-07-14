<template>
  <div class="data-chart" v-if="chartData">
    <div class="chart-header">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>
      </svg>
      <span>{{ chartData.title || '数据可视化' }}</span>
      <div class="chart-type-selector">
        <button class="chart-type-btn" :class="{ active: chartType === 'bar' }" @click="chartType = 'bar'" title="柱状图">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="10" width="4" height="10"/><rect x="10" y="5" width="4" height="15"/><rect x="17" y="14" width="4" height="6"/>
          </svg>
        </button>
        <button class="chart-type-btn" :class="{ active: chartType === 'line' }" @click="chartType = 'line'" title="折线图">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3 17 9 10 13 14 21 6"/>
          </svg>
        </button>
        <button class="chart-type-btn" :class="{ active: chartType === 'pie' }" @click="chartType = 'pie'" title="饼图">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z"/><path d="M21 12h-9V3"/>
          </svg>
        </button>
        <button class="chart-type-btn export-btn" @click="exportPNG" title="导出PNG">
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

/** 与数据看板一致的多彩调色板 */
const PALETTE = [
  '#4f46e5', '#06b6d4', '#10b981', '#f59e0b', '#ef4444',
  '#8b5cf6', '#ec4899', '#14b8a6', '#f97316', '#6366f1',
  '#0ea5e9', '#84cc16', '#e11d48', '#a855f7', '#22c55e',
]

const COLOR_SCHEMES = {
  rainbow: PALETTE,
  indigo: ['#4f46e5', '#6366f1', '#818cf8', '#a5b4fc', '#c7d2fe', '#06b6d4', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'],
  ocean: ['#06b6d4', '#0ea5e9', '#3b82f6', '#6366f1', '#8b5cf6', '#22d3ee', '#67e8f9', '#38bdf8', '#60a5fa', '#a78bfa'],
  forest: ['#10b981', '#14b8a6', '#06b6d4', '#84cc16', '#22c55e', '#34d399', '#2dd4bf', '#4ade80', '#a3e635', '#fbbf24'],
  sunset: ['#f59e0b', '#f97316', '#ef4444', '#ec4899', '#f43f5e', '#fbbf24', '#fb923c', '#f87171', '#f472b6', '#e879f9'],
  rose: ['#ef4444', '#f43f5e', '#ec4899', '#d946ef', '#f87171', '#fb7185', '#f472b6', '#e879f9', '#c084fc', '#a78bfa'],
  violet: ['#8b5cf6', '#a855f7', '#d946ef', '#6366f1', '#4f46e5', '#a78bfa', '#c084fc', '#e879f9', '#818cf8', '#6366f1'],
}

function hexToRgba(hex, alpha) {
  const h = hex.replace('#', '')
  const full = h.length === 3 ? h.split('').map((c) => c + c).join('') : h
  const n = parseInt(full, 16)
  const r = (n >> 16) & 255
  const g = (n >> 8) & 255
  const b = n & 255
  return `rgba(${r},${g},${b},${alpha})`
}

function getPalette() {
  const scheme = props.chartData?.colorScheme
  if (scheme && COLOR_SCHEMES[scheme]) return COLOR_SCHEMES[scheme]
  return PALETTE
}

function colorsForCount(n) {
  const base = getPalette()
  if (n <= 0) return base
  const out = []
  for (let i = 0; i < n; i++) out.push(base[i % base.length])
  return out
}

function buildDatasets(data) {
  const labels = data.labels || []
  const type = chartType.value
  const palette = getPalette()
  const multiCategory = labels.length > 1

  return (data.datasets || []).map((ds, i) => {
    const values = ds.data || []
    // 单序列 + 多类别：每根柱/每块饼不同色（对齐看板）
    const perItemColors = colorsForCount(Math.max(labels.length, values.length))

    if (type === 'pie') {
      return {
        label: ds.label,
        data: values,
        backgroundColor: perItemColors,
        borderColor: '#fff',
        borderWidth: 2,
        hoverOffset: 6,
      }
    }

    if (type === 'line') {
      const c = palette[i % palette.length]
      return {
        label: ds.label,
        data: values,
        borderColor: c,
        backgroundColor: hexToRgba(c, 0.12),
        borderWidth: 2.5,
        tension: 0.35,
        fill: true,
        pointBackgroundColor: c,
        pointBorderColor: '#fff',
        pointBorderWidth: 2,
        pointRadius: 4,
        pointHoverRadius: 6,
      }
    }

    // bar
    if (data.datasets.length === 1 && multiCategory) {
      // 多彩柱：每类一色
      return {
        label: ds.label,
        data: values,
        backgroundColor: perItemColors.map((c) => hexToRgba(c, 0.85)),
        borderColor: perItemColors,
        borderWidth: 1.5,
        borderRadius: 6,
        borderSkipped: false,
      }
    }

    // 多序列对比：每序列一色
    const c = palette[i % palette.length]
    return {
      label: ds.label,
      data: values,
      backgroundColor: hexToRgba(c, 0.82),
      borderColor: c,
      borderWidth: 1.5,
      borderRadius: 6,
      borderSkipped: false,
    }
  })
}

function renderChart() {
  if (!canvasRef.value || !props.chartData) return
  if (chartInstance) chartInstance.destroy()

  const ctx = canvasRef.value.getContext('2d')
  const data = props.chartData
  const type = chartType.value === 'pie' ? 'pie' : chartType.value === 'line' ? 'line' : 'bar'

  chartInstance = new Chart(ctx, {
    type,
    data: {
      labels: data.labels || [],
      datasets: buildDatasets(data),
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      aspectRatio: type === 'pie' ? 1.6 : 2,
      plugins: {
        title: {
          display: !!data.title,
          text: data.title || '',
          font: { size: 14, weight: '600' },
          color: '#334155',
          padding: { bottom: 16 },
        },
        legend: {
          position: 'bottom',
          labels: {
            font: { size: 12 },
            padding: 14,
            usePointStyle: true,
            // 单序列多彩柱时隐藏 legend（类目已在 x 轴）
            filter: (item, chart) => {
              if (type === 'bar' && (data.datasets || []).length === 1 && (data.labels || []).length > 1) {
                return false
              }
              return true
            },
          },
        },
        tooltip: {
          backgroundColor: 'rgba(15,23,42,0.9)',
          padding: 10,
          cornerRadius: 8,
          titleFont: { size: 12 },
          bodyFont: { size: 12 },
        },
      },
      scales: type !== 'pie' ? {
        x: {
          ticks: { font: { size: 11 }, color: '#64748b' },
          grid: { display: false },
          border: { display: false },
        },
        y: {
          ticks: { font: { size: 11 }, color: '#64748b' },
          grid: { color: '#f1f5f9' },
          border: { display: false },
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
onUnmounted(() => { if (chartInstance) chartInstance.destroy() })
</script>

<style scoped>
.data-chart {
  margin-top: 16px;
  background: linear-gradient(180deg, #fff, #f8fafc);
  border-radius: 14px;
  border: 1px solid #e2e8f0;
  overflow: hidden;
  animation: fadeIn 0.45s ease-out 0.1s both;
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.04);
}

@keyframes fadeIn {
  from { opacity: 0; transform: scale(0.98); }
  to { opacity: 1; transform: scale(1); }
}

.chart-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 14px;
  border-bottom: 1px solid #f1f5f9;
  font-size: 13px;
  font-weight: 600;
  color: #475569;
  background: #fff;
}

.chart-type-selector {
  margin-left: auto;
  display: flex;
  gap: 4px;
}

.chart-type-btn {
  padding: 5px 7px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  cursor: pointer;
  color: #64748b;
  transition: all 0.15s;
  display: flex;
  align-items: center;
}

.chart-type-btn:hover {
  border-color: #a5b4fc;
  color: #4f46e5;
  background: #eef2ff;
}

.chart-type-btn.active {
  background: linear-gradient(135deg, #4f46e5, #6366f1);
  border-color: transparent;
  color: #fff;
}

.chart-type-btn.export-btn:hover {
  border-color: #6ee7b7;
  color: #059669;
  background: #ecfdf5;
}

.chart-container {
  padding: 14px 16px 18px;
  max-height: 320px;
}
</style>
