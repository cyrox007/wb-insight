<script setup>
import { computed } from 'vue'
import CardLoaders from '../UI/Loaders/CardLoaders.vue'

const props = defineProps({
  chartData: {
    type: Array,
    default: () => [],
  },
  metrics: {
    type: Array,
    default: () => [],
  },
  isLoading: {
    type: Boolean,
    default: false,
  },
})

const hasData = computed(() => props.chartData.length > 0)
const visibleMetrics = computed(() => props.metrics.filter(metric => metric.visible !== false))

const maxAbsValue = computed(() => {
  const values = props.chartData.flatMap(item =>
    visibleMetrics.value
      .map(metric => Number(item?.[metric.key]))
      .filter(Number.isFinite)
  )
  if (!values.length) return 1
  return Math.max(1, ...values.map(value => Math.abs(value)))
})

const hasNegative = computed(() => props.chartData.some(item =>
  visibleMetrics.value.some(metric => Number(item?.[metric.key]) < 0)
))

const chartWidth = computed(() => Math.max(640, props.chartData.length * 58))

const getBarStyle = (value, color) => {
  const numericValue = Number(value)
  if (!Number.isFinite(numericValue)) return { display: 'none' }

  const normalized = Math.min(1, Math.abs(numericValue) / maxAbsValue.value)
  if (hasNegative.value) {
    const height = Math.max(2, normalized * 46)
    return numericValue >= 0
      ? { height: `${height}%`, bottom: '50%', backgroundColor: color }
      : { height: `${height}%`, top: '50%', backgroundColor: color }
  }

  return {
    height: `${Math.max(2, normalized * 88)}%`,
    bottom: '0',
    backgroundColor: color,
  }
}

const formatValue = (value, metric) => {
  const numericValue = Number(value)
  if (!Number.isFinite(numericValue)) return '—'
  const formatted = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 }).format(numericValue)
  if (metric.type === 'rub') return `${formatted} ₽`
  if (metric.type === 'percent') return `${formatted}%`
  return formatted
}

const shortDate = (value) => {
  if (!value) return '—'
  const text = String(value)
  return /^\d{4}-\d{2}-\d{2}/.test(text) ? text.slice(5, 10).split('-').reverse().join('.') : text
}
</script>

<template>
  <div class="daily-chart">
    <div class="legend" aria-label="Серии графика">
      <span v-for="metric in visibleMetrics" :key="metric.key" class="legend-item">
        <i :style="{ backgroundColor: metric.color }" />
        {{ metric.name }}
      </span>
    </div>

    <CardLoaders v-if="isLoading" />

    <div v-else-if="!hasData" class="chart-empty">
      <strong>Нет данных за выбранный период</strong>
      <span>После синхронизации здесь появится динамика по дням.</span>
    </div>

    <div v-else class="chart-scroll">
      <div class="chart-area" :style="{ width: `${chartWidth}px` }">
        <div class="grid-line grid-line--top" />
        <div class="grid-line grid-line--middle" />
        <div class="grid-line grid-line--bottom" />
        <div v-if="hasNegative" class="zero-line" />

        <div
          v-for="(day, dayIndex) in chartData"
          :key="`${day.date || 'day'}-${dayIndex}`"
          class="day-column"
        >
          <div class="bars">
            <div
              v-for="metric in visibleMetrics"
              :key="metric.key"
              class="bar-slot"
            >
              <div
                v-if="day[metric.key] !== null && day[metric.key] !== undefined"
                class="bar"
                :class="{ 'bar--negative': Number(day[metric.key]) < 0 }"
                :style="getBarStyle(day[metric.key], metric.color)"
              >
                <span class="tooltip">{{ metric.name }}: {{ formatValue(day[metric.key], metric) }}</span>
              </div>
            </div>
          </div>
          <span class="date-label">{{ shortDate(day.date) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.daily-chart {
  min-width: 0;
}

.legend {
  min-height: 28px;
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 600;
}

.legend-item i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
}

.chart-empty {
  min-height: 230px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 5px;
  border: 1px dashed var(--border-color);
  border-radius: 10px;
  background: rgba(15, 20, 28, 0.35);
  text-align: center;
}

.chart-empty strong {
  font-size: 13px;
}

.chart-empty span {
  color: var(--text-subtle);
  font-size: 11px;
}

.chart-scroll {
  width: 100%;
  overflow-x: auto;
  padding-bottom: 4px;
}

.chart-area {
  position: relative;
  min-width: 100%;
  height: 260px;
  padding: 14px 12px 30px;
  display: flex;
  align-items: stretch;
  gap: 4px;
  border: 1px solid rgba(148, 163, 184, 0.08);
  border-radius: 10px;
  background: rgba(15, 20, 28, 0.45);
}

.grid-line,
.zero-line {
  position: absolute;
  left: 12px;
  right: 12px;
  height: 1px;
  pointer-events: none;
}

.grid-line {
  background: rgba(148, 163, 184, 0.08);
}

.grid-line--top { top: 14px; }
.grid-line--middle { top: 50%; }
.grid-line--bottom { bottom: 30px; }

.zero-line {
  top: 50%;
  background: rgba(148, 163, 184, 0.22);
}

.day-column {
  position: relative;
  z-index: 1;
  min-width: 52px;
  flex: 1 0 52px;
  display: flex;
  flex-direction: column;
}

.bars {
  position: relative;
  flex: 1;
  display: flex;
  align-items: stretch;
  justify-content: center;
  gap: 3px;
}

.bar-slot {
  position: relative;
  width: 8px;
  height: 100%;
}

.bar {
  position: absolute;
  left: 0;
  width: 8px;
  min-height: 2px;
  border-radius: 3px 3px 1px 1px;
  opacity: 0.86;
  transition: opacity var(--transition), transform var(--transition);
}

.bar--negative {
  border-radius: 1px 1px 3px 3px;
}

.bar:hover {
  z-index: 5;
  opacity: 1;
  transform: scaleX(1.2);
}

.tooltip {
  position: absolute;
  left: 50%;
  bottom: calc(100% + 7px);
  z-index: 10;
  width: max-content;
  max-width: 220px;
  padding: 6px 8px;
  transform: translateX(-50%);
  border: 1px solid var(--border-color);
  border-radius: 7px;
  background: #111923;
  color: var(--text-color);
  box-shadow: var(--shadow);
  font-size: 10px;
  line-height: 1.3;
  opacity: 0;
  pointer-events: none;
}

.bar--negative .tooltip {
  top: calc(100% + 7px);
  bottom: auto;
}

.bar:hover .tooltip {
  opacity: 1;
}

.date-label {
  height: 22px;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  color: var(--text-subtle);
  font-size: 9px;
}

@media (max-width: 640px) {
  .chart-area {
    height: 230px;
  }
}
</style>
