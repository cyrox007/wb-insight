<template>
  <section class="overview-page dashboard-page" :class="{ 'is-refreshing': isLoading && hasLoadedOnce }">
    <header class="page-header">
      <div>
        <p class="eyebrow">Wildberries · аналитика кабинета</p>
        <h1>Обзор бизнеса</h1>
        <p class="page-subtitle">Главные показатели, динамика и точки, которые требуют внимания.</p>
        <div
          v-if="syncStatus && !isSyncing"
          class="sync-freshness"
          :class="`sync-freshness--${syncFreshnessTone}`"
          role="status"
          :aria-label="syncFreshnessAriaLabel"
        >
          <span class="sync-freshness__dot" aria-hidden="true"></span>
          <strong>{{ syncFreshnessHeadline }}</strong>
          <span>{{ syncFreshnessCaption }}</span>
        </div>
      </div>

      <form class="period-filter" @submit.prevent="applyPeriod">
        <label class="period-field">
          <span>С</span>
          <input v-model="startDate" type="date" :max="endDate" />
        </label>
        <label class="period-field">
          <span>По</span>
          <input v-model="endDate" type="date" :min="startDate" />
        </label>
        <button class="apply-button" type="submit" :disabled="isLoading || !periodIsValid">
          {{ isLoading ? 'Обновляем…' : 'Применить' }}
        </button>
      </form>
    </header>

    <DashboardState
      v-if="isLoading && !hasLoadedOnce"
      kind="loading"
    />

    <DashboardState
      v-else-if="errorMessage"
      kind="error"
      title="Не удалось загрузить аналитику"
      :message="errorMessage"
      action-label="Повторить"
      @retry="loadDashboard"
    />

    <div v-if="!errorMessage && (!isLoading || hasLoadedOnce) && isSyncing" class="status-banner" role="status">
      <strong>{{ syncMessage || 'Данные синхронизируются с Wildberries.' }}</strong>
      <span>{{ syncProgressText }}</span>
    </div>

    <div v-if="!errorMessage && (!isLoading || hasLoadedOnce) && !isInitialSync" class="kpi-grid" aria-label="Ключевые показатели">
      <article v-for="item in primaryKpis" :key="item.key" class="kpi-card">
        <div class="kpi-card__topline">
          <span>{{ item.label }}</span>
          <span v-if="item.change !== null" class="change-badge" :class="changeClass(item.change)">
            {{ formatChange(item.change) }}
          </span>
        </div>
        <div class="kpi-card__value">{{ formatMetric(item.value, item.format) }}</div>
        <p>{{ item.caption }}</p>
      </article>
    </div>

    <section v-if="!errorMessage && (!isLoading || hasLoadedOnce) && !isInitialSync" class="section-card plan-card">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Текущий месяц</p>
          <h2>План и темп</h2>
        </div>
        <div class="quality-pills" aria-label="Качество экономики">
          <span>Маржа <strong>{{ formatMetric(stats.marginality?.value, 'percent') }}</strong></span>
          <span>Рентабельность <strong>{{ formatMetric(stats.profitability?.value, 'percent') }}</strong></span>
          <span>ДРР <strong>{{ formatMetric(stats.ddr?.value, 'percent') }}</strong></span>
        </div>
      </div>

      <div class="plan-grid">
        <div class="plan-metric">
          <span>Факт</span>
          <strong>{{ formatMetric(stats.fact_current_month?.value, 'money') }}</strong>
        </div>
        <div class="plan-metric">
          <span>План</span>
          <strong>{{ formatMetric(stats.plan_current_month?.value, 'money') }}</strong>
        </div>
        <div class="plan-metric">
          <span>Выполнено</span>
          <strong>{{ formatMetric(stats.done?.value, 'percent') }}</strong>
        </div>
        <div class="plan-metric">
          <span>Прогноз выручки</span>
          <strong>{{ formatMetric(stats.forecast?.value, 'money') }}</strong>
        </div>
        <div class="plan-metric plan-metric--accent">
          <span>Нужно выручки в день</span>
          <strong>{{ formatMetric(stats.required_revenue_per_day?.value, 'money') }}</strong>
        </div>
        <div class="plan-metric plan-metric--accent">
          <span>Нужно заказов в день</span>
          <strong>{{ formatMetric(stats.required_orders_per_day?.value, 'number') }}</strong>
        </div>
      </div>
    </section>

    <section v-if="!errorMessage && (!isLoading || hasLoadedOnce) && !isInitialSync" class="analytics-grid">
      <article class="section-card chart-card">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Динамика</p>
            <h2>Продажи и прибыль</h2>
          </div>
        </div>
        <BaseCarts
          :is-loading="isLoading || isChartsLoading"
          :chart-data="chartData"
          :metrics="[
            { key: 'orders', name: 'Заказы, ₽', color: '#6259d9', visible: true, type: 'rub' },
            { key: 'buyouts', name: 'Выкупы, ₽', color: '#26a77b', visible: true, type: 'rub' },
            { key: 'profit', name: 'Прибыль, ₽', color: '#e26478', visible: true, type: 'rub' },
          ]"
        />
      </article>

      <article class="section-card chart-card">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Воронка</p>
            <h2>Интерес к товарам</h2>
          </div>
        </div>
        <BaseCarts
          :is-loading="isLoading || isChartsLoading"
          :chart-data="chartData"
          :metrics="[
            { key: 'views', name: 'Просмотры', color: '#4f86da', visible: true, type: 'number' },
            { key: 'clicks', name: 'Клики', color: '#d49a2b', visible: true, type: 'number' },
            { key: 'cart', name: 'В корзину', color: '#9a6bd9', visible: true, type: 'number' },
          ]"
        />
      </article>
    </section>

    <section v-if="!errorMessage && (!isLoading || hasLoadedOnce) && !isInitialSync" class="context-grid">
      <article class="section-card compact-card">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Остатки</p>
            <h2>По складам</h2>
          </div>
        </div>
        <WarehouseChart :data="warehouseData" :is-loading="isLoading || isChartsLoading" />
      </article>

      <article class="section-card compact-card">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Ассортимент</p>
            <h2>Категории</h2>
          </div>
        </div>
        <DonutChart :data="categoryData" :is-loading="isLoading || isChartsLoading" />
      </article>
    </section>

    <section v-if="!errorMessage && (!isLoading || hasLoadedOnce) && !isInitialSync" class="abc-section">
      <div class="section-heading section-heading--outside">
        <div>
          <p class="eyebrow">Товары</p>
          <h2>Что формирует результат</h2>
        </div>
        <span class="section-note">ABC-анализ за выбранный период</span>
      </div>
      <AbcAnalysis
        :items="abcAnalysis"
        :is-loading="isLoading || isChartsLoading"
        :has-data="abcAnalysis.length > 0"
      />
    </section>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import DashboardService from '@/API/Dashboard/DashboardService.js'
import { notify } from '@/composables/notification'
import BaseCarts from '@/components/Diagrams/BaseCarts.vue'
import WarehouseChart from '@/components/Diagrams/WarehouseChart.vue'
import AbcAnalysis from '@/components/Widgets/AbcAnalysis.vue'
import DonutChart from '@/components/Diagrams/DonutChart.vue'
import DashboardState from '@/components/DashboardState.vue'
import { formatFiniteNumber } from '@/utils/safeNumber'

const stats = ref({})
const chartData = ref([])
const abcAnalysis = ref([])
const warehouseData = ref([])
const categoryData = ref([])

const isLoading = ref(false)
const hasLoadedOnce = ref(false)
const isChartsLoading = ref(false)
const isSyncing = ref(false)
const isInitialSync = ref(false)
const syncStatus = ref(null)
const syncMessage = ref('')
const errorMessage = ref('')

const formatDateInput = (date) => {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

const today = new Date()
const initialStart = new Date(today)
initialStart.setDate(initialStart.getDate() - 29)

const startDate = ref(formatDateInput(initialStart))
const endDate = ref(formatDateInput(today))

const periodIsValid = computed(() => Boolean(startDate.value && endDate.value && startDate.value <= endDate.value))

const formatSyncTime = (value) => {
  if (!value) return ''
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return ''
  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(parsed)
}

const syncAttentionCount = computed(() => {
  if (!syncStatus.value) return 0
  return Number(syncStatus.value.stale_entities || 0) +
    Number(syncStatus.value.error_entities || 0) +
    Number(syncStatus.value.waiting_entities || 0)
})

const syncFreshnessTone = computed(() => {
  if (!syncStatus.value) return 'neutral'
  if (syncStatus.value.complete) return 'ready'
  if (Number(syncStatus.value.error_entities || 0) > 0) return 'error'
  return 'warning'
})

const syncFreshnessHeadline = computed(() => {
  if (!syncStatus.value) return ''
  if (syncStatus.value.complete) return 'Данные актуальны'
  return `Актуальность данных: ${syncStatus.value.ready_entities || 0}/${syncStatus.value.total_entities || 0}`
})

const syncFreshnessCaption = computed(() => {
  if (!syncStatus.value) return ''
  const oldest = formatSyncTime(syncStatus.value.oldest_success_at)
  const interval = Number(syncStatus.value.freshness_interval_hours || 0)
  const intervalText = interval
    ? `интервал тарифа: ${interval} ч`
    : syncStatus.value.freshness_policy_available === false
      ? 'интервал тарифа не настроен'
      : ''

  if (syncStatus.value.complete) {
    const freshness = oldest ? `все источники обновлены не раньше ${oldest}` : 'все источники синхронизированы'
    return intervalText ? `${freshness} · ${intervalText}` : freshness
  }

  const parts = []
  if (syncStatus.value.stale_entities) parts.push(`устарели: ${syncStatus.value.stale_entities}`)
  if (syncStatus.value.error_entities) parts.push(`ошибки: ${syncStatus.value.error_entities}`)
  if (syncStatus.value.waiting_entities) parts.push(`ожидают: ${syncStatus.value.waiting_entities}`)
  if (intervalText) parts.push(intervalText)
  const latest = formatSyncTime(syncStatus.value.latest_success_at)
  const detail = parts.length ? parts.join(' · ') : `требуют внимания: ${syncAttentionCount.value}`
  return latest ? `${detail} · последнее успешное обновление ${latest}` : detail
})

const syncFreshnessAriaLabel = computed(() =>
  [syncFreshnessHeadline.value, syncFreshnessCaption.value].filter(Boolean).join('. ')
)

const syncProgressText = computed(() => {
  if (!isInitialSync.value) {
    return 'Показаны последние успешно сохранённые данные. Обновление идёт в фоне.'
  }
  if (!syncStatus.value) return 'Показатели появятся автоматически после завершения синхронизации.'
  const ready = Number(syncStatus.value.ready_entities || 0)
  const total = Number(syncStatus.value.total_entities || 0)
  if (!total) return 'Показатели появятся автоматически после завершения синхронизации.'
  return `Готово источников: ${ready} из ${total}. Показатели обновятся автоматически.`
})

const primaryKpis = computed(() => [
  {
    key: 'ordered_amount',
    label: 'Заказано',
    value: stats.value.ordered_amount?.value,
    change: stats.value.ordered_amount?.change_percent ?? null,
    format: 'money',
    caption: `${formatMetric(stats.value.ordered_units?.value, 'number')} ед. заказано`,
  },
  {
    key: 'revenue',
    label: 'Выручка',
    value: stats.value.revenue?.value,
    change: stats.value.revenue?.change_percent ?? null,
    format: 'money',
    caption: `${formatMetric(stats.value.sold_units?.value, 'number')} ед. продано`,
  },
  {
    key: 'profit',
    label: 'Прибыль',
    value: stats.value.profit?.value,
    change: stats.value.profit?.change_percent ?? null,
    format: 'money',
    caption: 'После себестоимости и учтённых расходов',
  },
  {
    key: 'to_pay',
    label: 'К выплате',
    value: stats.value.to_pay?.value,
    change: stats.value.to_pay?.change_percent ?? null,
    format: 'money',
    caption: 'По финансовому отчёту WB',
  },
  {
    key: 'buyout_rate',
    label: 'Выкуп',
    value: stats.value.buyout_rate?.value,
    change: stats.value.buyout_rate?.change_percent ?? null,
    format: 'percent',
    caption: 'Продажи относительно заказов',
  },
  {
    key: 'avg_price',
    label: 'Средняя цена заказа',
    value: stats.value.avg_price?.value,
    change: stats.value.avg_price?.change_percent ?? null,
    format: 'money',
    caption: 'Средняя сумма на заказанную единицу',
  },
])

function formatNumber(value, maximumFractionDigits = 2) {
  return formatFiniteNumber(value, { maximumFractionDigits })
}

function formatMetric(value, format = 'number') {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—'
  if (format === 'money') return `${formatNumber(value)} ₽`
  if (format === 'percent') return `${formatNumber(value, 1)}%`
  return formatNumber(value)
}

function formatChange(change) {
  const value = Number(change)
  if (!Number.isFinite(value)) return '—'
  const prefix = value > 0 ? '+' : ''
  return `${prefix}${formatNumber(value, 1)}%`
}

function changeClass(change) {
  const value = Number(change)
  if (value > 0) return 'change-badge--positive'
  if (value < 0) return 'change-badge--negative'
  return 'change-badge--neutral'
}

function extractError(result, fallback = 'Попробуйте обновить страницу.') {
  return result?.error?.message || result?.message || fallback
}

async function loadCharts() {
  isChartsLoading.value = true
  try {
    const response = await DashboardService.get_dashboard_charts({
      start_date: startDate.value,
      end_date: endDate.value,
    })
    const result = response.data
    if (result?.status === 'error') return

    chartData.value = result.chartData || []
    warehouseData.value = result.warehouseData || []
    categoryData.value = result.categoryData || []
    abcAnalysis.value = result.abcAnalysis || []
  } catch (error) {
    console.error('Ошибка загрузки графиков:', error)
  } finally {
    isChartsLoading.value = false
  }
}

async function loadDashboard() {
  if (!periodIsValid.value) {
    errorMessage.value = 'Проверьте выбранный диапазон дат.'
    return
  }

  isLoading.value = true
  errorMessage.value = ''
  isSyncing.value = false
  isInitialSync.value = false
  syncMessage.value = ''
  try {
    const response = await DashboardService.get_dashboard_data({
      start_date: startDate.value,
      end_date: endDate.value,
    })
    const result = response.data

    if (result?.status === 'error') {
      stats.value = {}
      syncStatus.value = null
      isInitialSync.value = false
      errorMessage.value = extractError(result)
      return
    }

    stats.value = result.stats || {}
    syncStatus.value = result.sync_status || null
    syncMessage.value = result.message || ''
    isSyncing.value = result.is_syncing === true || result.is_synced === false
    isInitialSync.value = result.initial_sync === true

    if (isInitialSync.value) {
      chartData.value = []
      warehouseData.value = []
      categoryData.value = []
      abcAnalysis.value = []
      return
    }

    await loadCharts()
  } catch (error) {
    const message = error.response?.data?.error?.message || 'Сервис временно недоступен. Попробуйте ещё раз.'
    errorMessage.value = message
    notify.error(message, 3000)
  } finally {
    isLoading.value = false
    hasLoadedOnce.value = true
  }
}

async function applyPeriod() {
  await loadDashboard()
}

onMounted(loadDashboard)
</script>

<style scoped>
.overview-page {
  width: min(100% - 32px, var(--content-width));
  margin: 0 auto;
  padding: 22px 0 48px;
}

.page-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 18px;
}

.page-header h1 {
  margin-top: 3px;
  font-size: clamp(26px, 3vw, 36px);
  line-height: 1.08;
  letter-spacing: -0.035em;
}

.eyebrow {
  color: #6259d9;
  font-size: 11px;
  font-weight: 750;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.page-subtitle {
  max-width: 620px;
  margin-top: 8px;
  color: var(--text-muted);
  font-size: 14px;
}

.sync-freshness {
  width: fit-content;
  max-width: 100%;
  margin-top: 10px;
  padding: 6px 9px;
  display: flex;
  align-items: center;
  gap: 7px;
  border: 1px solid var(--border-color);
  border-radius: 999px;
  background: var(--card-bg);
  color: var(--text-muted);
  font-size: 11px;
  line-height: 1.35;
}

.sync-freshness strong {
  color: var(--text-color);
  font-weight: 700;
}

.sync-freshness__dot {
  width: 7px;
  height: 7px;
  flex: 0 0 auto;
  border-radius: 50%;
  background: var(--text-subtle);
}

.sync-freshness--ready .sync-freshness__dot {
  background: #22a06b;
}

.sync-freshness--warning .sync-freshness__dot {
  background: #d49a2b;
}

.sync-freshness--error .sync-freshness__dot {
  background: var(--danger-color);
}

.period-filter {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  padding: 8px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  background: var(--card-bg);
}

.period-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.period-field span {
  color: var(--text-subtle);
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
}

.period-field input {
  min-height: 36px;
  padding: 7px 9px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--light-bg);
  color: var(--text-color);
}

.apply-button {
  min-height: 36px;
  padding: 7px 13px;
  border: 1px solid var(--secondary-color);
  border-radius: 8px;
  background: var(--secondary-color);
  color: #fff;
  font-weight: 650;
  cursor: pointer;
}

.apply-button:hover:not(:disabled) {
  background: var(--secondary-hover);
}

.apply-button:disabled {
  opacity: 0.55;
  cursor: default;
}

.status-banner {
  margin-bottom: 16px;
  padding: 13px 15px;
  display: flex;
  align-items: center;
  gap: 8px;
  border: 1px solid rgba(96, 165, 250, 0.28);
  border-radius: var(--radius);
  background: rgba(96, 165, 250, 0.08);
  color: #3568a8;
  font-size: 13px;
}

.status-banner span {
  color: var(--text-muted);
}

.status-banner button {
  margin-left: auto;
  padding: 6px 9px;
  border: 1px solid currentColor;
  border-radius: 7px;
  background: transparent;
  color: inherit;
  cursor: pointer;
}

.status-banner--error {
  border-color: rgba(251, 113, 133, 0.3);
  background: rgba(251, 113, 133, 0.08);
  color: #c83b55;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 10px;
}

.kpi-card,
.section-card {
  border: 1px solid var(--border-color);
  background: linear-gradient(180deg, var(--card-bg-elevated), var(--card-bg));
  box-shadow: var(--shadow-sm);
}

.kpi-card {
  min-height: 132px;
  padding: 15px;
  border-radius: var(--radius);
}

.kpi-card__topline {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 650;
}

.kpi-card__value {
  margin-top: 14px;
  font-size: clamp(21px, 2vw, 27px);
  font-weight: 760;
  line-height: 1;
  letter-spacing: -0.025em;
}

.kpi-card p {
  margin-top: 11px;
  color: var(--text-subtle);
  font-size: 11px;
  line-height: 1.35;
}

.change-badge {
  padding: 3px 6px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 750;
}

.change-badge--positive {
  background: rgba(52, 211, 153, 0.1);
  color: #16805f;
}

.change-badge--negative {
  background: rgba(251, 113, 133, 0.1);
  color: #c83b55;
}

.change-badge--neutral {
  background: rgba(148, 163, 184, 0.1);
  color: var(--text-muted);
}

.section-card {
  border-radius: var(--radius-lg);
  padding: 18px;
}

.plan-card {
  margin-top: 12px;
}

.section-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 14px;
}

.section-heading h2 {
  margin-top: 2px;
  font-size: 17px;
  font-weight: 720;
  letter-spacing: -0.015em;
}

.quality-pills {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 6px;
}

.quality-pills span {
  padding: 6px 8px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  color: var(--text-subtle);
  font-size: 11px;
}

.quality-pills strong {
  margin-left: 4px;
  color: var(--text-color);
}

.plan-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 8px;
}

.plan-metric {
  min-height: 78px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  border-radius: 10px;
  background: rgba(239, 242, 249, 0.9);
}

.plan-metric span {
  color: var(--text-subtle);
  font-size: 10px;
}

.plan-metric strong {
  margin-top: 8px;
  font-size: 15px;
  font-weight: 700;
}

.plan-metric--accent {
  background: rgba(124, 58, 237, 0.09);
}

.analytics-grid,
.context-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 12px;
}

.chart-card {
  min-width: 0;
}

.compact-card {
  min-width: 0;
  min-height: 300px;
}

.abc-section {
  margin-top: 18px;
}

.section-heading--outside {
  margin: 0 2px 10px;
}

.section-note {
  color: var(--text-subtle);
  font-size: 11px;
}

@media (max-width: 1220px) {
  .kpi-grid,
  .plan-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 860px) {
  .page-header {
    align-items: stretch;
    flex-direction: column;
  }

  .period-filter {
    width: 100%;
  }

  .sync-freshness {
    width: 100%;
    border-radius: 10px;
    flex-wrap: wrap;
  }

  .period-field {
    flex: 1;
  }

  .period-field input {
    width: 100%;
  }

  .analytics-grid,
  .context-grid {
    grid-template-columns: 1fr;
  }

  .quality-pills {
    justify-content: flex-start;
  }

  .section-heading {
    flex-direction: column;
  }
}

@media (max-width: 620px) {
  .overview-page {
    width: min(100% - 20px, var(--content-width));
    padding-top: 16px;
  }

  .period-filter {
    display: grid;
    grid-template-columns: 1fr 1fr;
  }

  .apply-button {
    grid-column: 1 / -1;
  }

  .kpi-grid,
  .plan-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .kpi-card {
    min-height: 120px;
  }

  .status-banner {
    align-items: flex-start;
    flex-direction: column;
  }

  .status-banner button {
    margin-left: 0;
  }
}

@media (max-width: 390px) {
  .kpi-grid,
  .plan-grid {
    grid-template-columns: 1fr;
  }
}
</style>
