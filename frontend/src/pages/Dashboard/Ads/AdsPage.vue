<template>
  <section class="ads-page dashboard-page" :class="{ 'is-refreshing': isLoading && hasLoadedOnce }">
    <header class="page-header">
      <div>
        <p class="eyebrow">Продвижение</p>
        <h1>Реклама</h1>
        <p class="page-subtitle">Расходы, воронка и эффективность рекламных заказов без лишних показателей.</p>
      </div>

      <form class="period-filter" @submit.prevent="loadData">
        <label>
          <span>С</span>
          <input v-model="startDate" type="date" :max="endDate" />
        </label>
        <label>
          <span>По</span>
          <input v-model="endDate" type="date" :min="startDate" />
        </label>
        <button type="submit" :disabled="isLoading || !periodIsValid">
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
      title="Не удалось загрузить рекламу"
      :message="errorMessage"
      action-label="Повторить"
      @retry="loadData"
    />

    <DashboardState
      v-else-if="!hasData && hasLoadedOnce"
      kind="empty"
      title="Пока нет рекламной статистики"
      message="Данные появятся после первой успешной синхронизации Promotion API Wildberries."
    />

    <template v-else>
      <div class="kpi-grid">
        <article v-for="item in summaryKpis" :key="item.label" class="kpi-card">
          <span>{{ item.label }}</span>
          <strong>{{ formatMetric(item.value, item.type) }}</strong>
          <small>{{ item.caption }}</small>
        </article>
      </div>

      <div class="insight-grid">
        <article class="section-card">
          <div class="section-heading">
            <div>
              <p class="eyebrow">Воронка рекламы</p>
              <h2>От показа до заказа</h2>
            </div>
          </div>

          <div class="metric-list">
            <div class="metric-row"><span>Просмотры</span><strong>{{ formatNumber(funnel.views) }}</strong></div>
            <div class="metric-row"><span>Клики</span><strong>{{ formatNumber(funnel.clicks) }}</strong></div>
            <div class="metric-row"><span>В корзину</span><strong>{{ formatNumber(funnel.added_to_cart) }}</strong></div>
            <div class="metric-row metric-row--accent"><span>Заказы из рекламы</span><strong>{{ formatNumber(funnel.ad_orders) }}</strong></div>
            <div class="metric-row"><span>Сумма рекламных заказов</span><strong>{{ formatMetric(funnel.ad_orders_amount, 'money') }}</strong></div>
            <div class="metric-row"><span>Все заказы кабинета</span><strong>{{ formatNumber(funnel.total_orders) }}</strong></div>
            <div class="metric-row"><span>Сумма всех заказов</span><strong>{{ formatMetric(funnel.total_orders_amount, 'money') }}</strong></div>
          </div>
        </article>

        <article class="section-card">
          <div class="section-heading">
            <div>
              <p class="eyebrow">Эффективность</p>
              <h2>Стоимость и конверсия</h2>
            </div>
          </div>

          <div class="metric-list">
            <div class="metric-row"><span>CTR</span><strong>{{ formatMetric(conversions.ctr, 'percent') }}</strong></div>
            <div class="metric-row"><span>CR в корзину</span><strong>{{ formatMetric(conversions.cr_to_cart, 'percent') }}</strong></div>
            <div class="metric-row"><span>Клик → заказ</span><strong>{{ formatMetric(conversions.conversion_click_to_order, 'percent') }}</strong></div>
            <div class="metric-row"><span>CPC</span><strong>{{ formatMetric(conversions.cpc, 'money') }}</strong></div>
            <div class="metric-row"><span>CPM</span><strong>{{ formatMetric(conversions.cpm, 'money') }}</strong></div>
            <div class="metric-row metric-row--accent"><span>CPO</span><strong>{{ formatMetric(acquisitionCost.cpo, 'money') }}</strong></div>
            <div class="metric-row metric-row--accent"><span>ДРР</span><strong>{{ formatMetric(conversions.drr, 'percent') }}</strong></div>
          </div>
        </article>
      </div>

      <section class="section-card chart-card">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Динамика</p>
            <h2>Трафик и расходы</h2>
          </div>
        </div>
        <BaseCarts
          :is-loading="isLoading"
          :chart-data="dynamicsChart"
          :metrics="[
            { key: 'views', name: 'Просмотры', color: '#4f86da', visible: true, type: 'number' },
            { key: 'clicks', name: 'Клики', color: '#d49a2b', visible: true, type: 'number' },
            { key: 'amount', name: 'Расходы, ₽', color: '#e26478', visible: true, type: 'rub' },
          ]"
        />
      </section>

      <section class="table-card">
        <div class="section-heading section-heading--table">
          <div>
            <p class="eyebrow">Товары</p>
            <h2>Эффективность по артикулам</h2>
          </div>
          <span>{{ articlesTable.length }} позиций</span>
        </div>

        <div v-if="!articlesTable.length" class="table-empty">Нет данных по артикулам за выбранный период.</div>
        <div v-else class="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Товар</th>
                <th>nmId</th>
                <th>Просмотры</th>
                <th>Клики</th>
                <th>В корзину</th>
                <th>Заказы из рекламы</th>
                <th>Расходы</th>
                <th>CPC</th>
                <th>CPO</th>
                <th>ДРР от всех заказов</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in articlesTable" :key="item.nm_id">
                <td class="product-cell">{{ item.product_name || 'Без названия' }}</td>
                <td>{{ item.nm_id }}</td>
                <td>{{ formatNumber(item.views) }}</td>
                <td>{{ formatNumber(item.clicks) }}</td>
                <td>{{ formatNumber(item.added_to_cart) }}</td>
                <td>{{ formatNumber(item.ad_orders) }}</td>
                <td>{{ formatMetric(item.expenses, 'money') }}</td>
                <td>{{ formatMetric(item.cpc, 'money') }}</td>
                <td>{{ formatMetric(item.order_cost_in_ads, 'money') }}</td>
                <td>{{ formatMetric(item.drr_from_orders, 'percent') }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import AdsService from '@/API/Dashboard/AdsService.js'
import { notify } from '@/composables/notification'
import BaseCarts from '@/components/Diagrams/BaseCarts.vue'
import DashboardState from '@/components/DashboardState.vue'

const isLoading = ref(false)
const hasLoadedOnce = ref(false)
const errorMessage = ref('')

const funnel = ref({})
const conversions = ref({})
const acquisitionCost = ref({})
const dynamicsChart = ref([])
const articlesTable = ref([])

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

const hasData = computed(() => Boolean(
  Object.keys(funnel.value || {}).length ||
  Object.keys(conversions.value || {}).length ||
  Object.keys(acquisitionCost.value || {}).length ||
  dynamicsChart.value.length ||
  articlesTable.value.length
))

const summaryKpis = computed(() => [
  {
    label: 'Расходы',
    value: conversions.value.expenses,
    type: 'money',
    caption: 'Фактический рекламный расход',
  },
  {
    label: 'Заказы из рекламы',
    value: funnel.value.ad_orders,
    type: 'number',
    caption: 'Атрибутированные рекламой',
  },
  {
    label: 'CPO',
    value: acquisitionCost.value.cpo,
    type: 'money',
    caption: 'Стоимость рекламного заказа',
  },
  {
    label: 'ДРР',
    value: conversions.value.drr,
    type: 'percent',
    caption: 'Расходы к рекламным продажам',
  },
  {
    label: 'CTR',
    value: conversions.value.ctr,
    type: 'percent',
    caption: 'Клики относительно показов',
  },
  {
    label: 'CPC',
    value: conversions.value.cpc,
    type: 'money',
    caption: 'Средняя стоимость клика',
  },
])

const formatNumber = (value, maximumFractionDigits = 2) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—'
  return new Intl.NumberFormat('ru-RU', { maximumFractionDigits }).format(Number(value))
}

const formatMetric = (value, type = 'number') => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—'
  if (type === 'money') return `${formatNumber(value)} ₽`
  if (type === 'percent') return `${formatNumber(value, 1)}%`
  return formatNumber(value)
}

const loadData = async () => {
  if (!periodIsValid.value) {
    errorMessage.value = 'Проверьте выбранный диапазон дат.'
    return
  }

  isLoading.value = true
  errorMessage.value = ''
  try {
    const response = await AdsService.get_ads_stats({
      start_date: startDate.value,
      end_date: endDate.value,
    })
    const result = response.data

    if (result.status === 'error') {
      funnel.value = {}
      conversions.value = {}
      acquisitionCost.value = {}
      dynamicsChart.value = []
      articlesTable.value = []
      errorMessage.value = result.error?.message || 'Нет данных рекламы за выбранный период.'
      return
    }

    funnel.value = result.data?.funnel || {}
    conversions.value = result.data?.conversions || {}
    acquisitionCost.value = result.data?.acquisition_cost || {}
    dynamicsChart.value = result.data?.dynamics_chart || []
    articlesTable.value = result.data?.articles_table || []
  } catch (error) {
    console.error('Ошибка загрузки данных рекламы:', error)
    errorMessage.value = error.response?.data?.error?.message || 'Сервис рекламы временно недоступен.'
    notify.error(errorMessage.value, 3000)
  } finally {
    isLoading.value = false
    hasLoadedOnce.value = true
  }
}

onMounted(loadData)
</script>

<style scoped>
.ads-page {
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
  max-width: 680px;
  margin-top: 8px;
  color: var(--text-muted);
  font-size: 14px;
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

.period-filter label {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.period-filter label span {
  color: var(--text-subtle);
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
}

.period-filter input,
.period-filter button {
  min-height: 36px;
  border-radius: 8px;
}

.period-filter input {
  padding: 7px 9px;
  border: 1px solid var(--border-color);
  background: var(--light-bg);
  color: var(--text-color);
}

.period-filter button {
  padding: 7px 13px;
  border: 1px solid var(--secondary-color);
  background: var(--secondary-color);
  color: #fff;
  font-weight: 650;
  cursor: pointer;
}

.period-filter button:disabled {
  opacity: 0.55;
  cursor: default;
}

.status-banner,
.empty-state {
  padding: 14px 15px;
  display: flex;
  align-items: center;
  gap: 8px;
  border-radius: var(--radius);
  font-size: 13px;
}

.status-banner {
  border: 1px solid rgba(251, 113, 133, 0.28);
  background: rgba(251, 113, 133, 0.08);
  color: #c83b55;
}

.status-banner span,
.empty-state span {
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

.empty-state {
  border: 1px solid var(--border-color);
  background: var(--card-bg);
  color: var(--text-color);
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 10px;
}

.kpi-card,
.section-card,
.table-card {
  border: 1px solid var(--border-color);
  background: linear-gradient(180deg, var(--card-bg-elevated), var(--card-bg));
  box-shadow: var(--shadow-sm);
}

.kpi-card {
  min-height: 120px;
  padding: 15px;
  display: flex;
  flex-direction: column;
  border-radius: var(--radius);
}

.kpi-card > span {
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 650;
}

.kpi-card strong {
  margin-top: 13px;
  font-size: clamp(20px, 2vw, 26px);
  letter-spacing: -0.025em;
}

.kpi-card small {
  margin-top: auto;
  padding-top: 10px;
  color: var(--text-subtle);
  font-size: 10px;
  line-height: 1.35;
}

.insight-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 12px;
}

.section-card,
.table-card {
  padding: 18px;
  border-radius: var(--radius-lg);
}

.chart-card,
.table-card {
  margin-top: 12px;
}

.section-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.section-heading h2 {
  margin-top: 2px;
  font-size: 17px;
  font-weight: 720;
}

.section-heading--table > span {
  color: var(--text-subtle);
  font-size: 11px;
}

.metric-list {
  display: flex;
  flex-direction: column;
}

.metric-row {
  min-height: 42px;
  padding: 8px 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.09);
}

.metric-row:last-child {
  border-bottom: 0;
}

.metric-row span {
  color: var(--text-muted);
  font-size: 12px;
}

.metric-row strong {
  font-size: 13px;
}

.metric-row--accent strong {
  color: #5b52d6;
}

.table-wrapper {
  overflow-x: auto;
}

table {
  width: 100%;
  min-width: 940px;
  border-collapse: collapse;
  font-size: 12px;
}

th,
td {
  padding: 11px 10px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.1);
  text-align: right;
  white-space: nowrap;
}

th {
  color: var(--text-subtle);
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
}

th:first-child,
td:first-child {
  text-align: left;
}

.product-cell {
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.table-empty {
  padding: 28px 8px;
  color: var(--text-subtle);
  text-align: center;
  font-size: 12px;
}

@media (max-width: 1220px) {
  .kpi-grid {
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

  .period-filter label {
    flex: 1;
  }

  .period-filter input {
    width: 100%;
  }

  .insight-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .ads-page {
    width: min(100% - 20px, var(--content-width));
    padding-top: 16px;
  }

  .kpi-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .period-filter {
    display: grid;
    grid-template-columns: 1fr 1fr;
  }

  .period-filter button {
    grid-column: 1 / -1;
  }

  .status-banner,
  .empty-state {
    align-items: flex-start;
    flex-direction: column;
  }

  .status-banner button {
    margin-left: 0;
  }
}
</style>
