<script setup>
import { computed, onMounted, ref } from 'vue'
import UnityEconomyService from '@/API/Dashboard/UnityEconomyService'
import UnitEconomyBlock from '@/components/Widgets/UnitEconomyBlock.vue'
import BaseCarts from '@/components/Diagrams/BaseCarts.vue'
import UnitEconomyTable from '@/components/Widgets/UnitEconomyTable.vue'
import { notify } from '@/composables/notification'
import DashboardState from '@/components/DashboardState.vue'

const isLoading = ref(false)
const hasLoadedOnce = ref(false)
const errorMessage = ref('')
const unityData = ref(null)
const tableData = ref([])
const dailyData = ref([])

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

const formatNumber = (value, maximumFractionDigits = 2) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—'
  return new Intl.NumberFormat('ru-RU', { maximumFractionDigits }).format(Number(value))
}

const formatMetric = (value, type = 'number') => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—'
  if (type === 'currency') return `${formatNumber(value)} ₽`
  if (type === 'percent') return `${formatNumber(value, 1)}%`
  return formatNumber(value)
}

const summaryKpis = computed(() => {
  const d = unityData.value || {}
  return [
    { label: 'Продажи с СПП', value: d.sales_with_spp, type: 'currency' },
    { label: 'Прибыль', value: d.profit, type: 'currency' },
    { label: 'Маржинальность', value: d.marginality, type: 'percent' },
    { label: 'Рентабельность', value: d.profitability, type: 'percent' },
  ]
})

const block1Rows = computed(() => {
  if (!unityData.value) return []
  const d = unityData.value
  return [
    { label: 'Продажи с СПП', value: d.sales_with_spp, type: 'currency' },
    { label: '', value: null, divider: true },
    { label: 'Комиссия WB', value: d.wb_commission_percent, type: 'percent' },
    { label: 'Комиссия WB, сумма', value: d.wb_commission_amount, type: 'currency' },
    { label: 'К перечислению продавцу', value: d.to_pay_seller, type: 'currency', highlight: true },
    { label: '', value: null, divider: true },
    { label: 'Логистика', value: d.logistics, type: 'currency' },
    { label: 'Хранение', value: d.storage, type: 'currency' },
    { label: 'Прочие удержания', value: d.other_deductions, type: 'currency' },
    { label: 'Штрафы', value: d.fines, type: 'currency' },
    { label: 'Платная приёмка', value: d.paid_acceptance, type: 'currency' },
  ]
})

const block2Rows = computed(() => {
  if (!unityData.value) return []
  const d = unityData.value
  return [
    { label: 'Средняя цена продажи', value: d.avg_sale_price, type: 'currency' },
    { label: 'Налог', value: d.tax, type: 'currency' },
    { label: 'Прочие расходы', value: d.other_expenses, type: 'currency' },
    { label: 'ДРР', value: d.drr, type: 'percent' },
    { label: '', value: null, divider: true },
    { label: 'Себестоимость', value: d.cost_price, type: 'currency' },
    { label: 'Прибыль на единицу', value: d.profit_per_unit, type: 'currency', positive: true },
    { label: 'Прибыль', value: d.profit, type: 'currency', positive: true },
    { label: 'Маржинальность', value: d.marginality, type: 'percent', highlight: true },
    { label: 'Рентабельность', value: d.profitability, type: 'percent', highlight: true },
  ]
})

const chartMetrics = [
  { key: 'to_pay_accumulated', name: 'К выплате', color: '#6259d9', visible: true, type: 'rub' },
  { key: 'logistics', name: 'Логистика', color: '#4f86da', visible: true, type: 'rub' },
  { key: 'fines', name: 'Штрафы', color: '#e26478', visible: true, type: 'rub' },
  { key: 'to_pay_seller', name: 'К перечислению', color: '#26a77b', visible: true, type: 'rub' },
]

const chartData = computed(() => dailyData.value.map(day => ({
  date: day.date,
  to_pay_accumulated: day.to_pay_accumulated,
  fines: day.fines,
  logistics: day.logistics,
  to_pay_seller: day.to_pay_seller,
})))

const loadData = async () => {
  if (!periodIsValid.value) {
    errorMessage.value = 'Проверьте выбранный диапазон дат.'
    return
  }

  isLoading.value = true
  errorMessage.value = ''
  try {
    const response = await UnityEconomyService.get_unity_economy_table({
      start_date: startDate.value,
      end_date: endDate.value,
    })
    const result = response.data

    if (result.status === 'error') {
      unityData.value = null
      tableData.value = []
      dailyData.value = []
      errorMessage.value = result.error?.message || 'Не удалось загрузить юнит-экономику.'
      return
    }

    unityData.value = result.data?.summary || {}
    tableData.value = result.data?.table || []
    dailyData.value = result.data?.daily_data || []
  } catch (error) {
    console.error('Ошибка загрузки юнит-экономики:', error)
    errorMessage.value = error.response?.data?.error?.message || 'Сервис временно недоступен.'
    notify.error(errorMessage.value, 3000)
  } finally {
    isLoading.value = false
    hasLoadedOnce.value = true
  }
}

onMounted(loadData)
</script>

<template>
  <section class="unit-page">
    <header class="page-header">
      <div>
        <p class="eyebrow">P&L по товарам</p>
        <h1>Юнит-экономика</h1>
        <p class="page-subtitle">Сколько остаётся после комиссии, логистики, рекламы, налогов, себестоимости и ваших расходов.</p>
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
      title="Не удалось рассчитать юнит-экономику"
      :message="errorMessage"
      action-label="Повторить"
      @retry="loadData"
    />

    <DashboardState
      v-else-if="hasLoadedOnce && !unityData"
      kind="empty"
      title="Нет данных для расчёта"
      message="После синхронизации продаж, финансовых удержаний и себестоимости здесь появится юнит-экономика."
    />

    <template v-else>
      <div class="summary-grid">
        <article v-for="item in summaryKpis" :key="item.label" class="summary-card">
          <span>{{ item.label }}</span>
          <strong>{{ formatMetric(item.value, item.type) }}</strong>
        </article>
      </div>

      <div class="detail-grid">
        <UnitEconomyBlock title="Финансы WB" :rows="block1Rows" :is-loading="isLoading" />
        <UnitEconomyBlock title="Расходы и прибыль" :rows="block2Rows" :is-loading="isLoading" />
      </div>

      <section v-if="chartData.length" class="chart-card">
        <div class="section-heading">
          <p class="eyebrow">Динамика</p>
          <h2>Выплаты и расходы</h2>
        </div>
        <BaseCarts :chart-data="chartData" :metrics="chartMetrics" :is-loading="isLoading" />
      </section>

      <section class="table-card">
        <div class="section-heading">
          <p class="eyebrow">Детализация</p>
          <h2>По артикулам</h2>
        </div>
        <UnitEconomyTable :data="tableData" :is-loading="isLoading" />
      </section>
    </template>
  </section>
</template>

<style scoped>
.unit-page {
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
  max-width: 700px;
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

.status-banner {
  padding: 14px 15px;
  display: flex;
  align-items: center;
  gap: 8px;
  border: 1px solid rgba(251, 113, 133, 0.28);
  border-radius: var(--radius);
  background: rgba(251, 113, 133, 0.08);
  color: #c83b55;
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

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.summary-card,
.chart-card,
.table-card {
  border: 1px solid var(--border-color);
  background: linear-gradient(180deg, var(--card-bg-elevated), var(--card-bg));
  box-shadow: var(--shadow-sm);
}

.summary-card {
  min-height: 98px;
  padding: 15px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  border-radius: var(--radius);
}

.summary-card span {
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 650;
}

.summary-card strong {
  margin-top: 10px;
  font-size: clamp(20px, 2vw, 27px);
  letter-spacing: -0.025em;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 12px;
}

.chart-card,
.table-card {
  margin-top: 12px;
  padding: 18px;
  border-radius: var(--radius-lg);
}

.section-heading {
  margin-bottom: 12px;
}

.section-heading h2 {
  margin-top: 2px;
  font-size: 17px;
  font-weight: 720;
}

@media (max-width: 900px) {
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

  .detail-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .unit-page {
    width: min(100% - 20px, var(--content-width));
    padding-top: 16px;
  }

  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .period-filter {
    display: grid;
    grid-template-columns: 1fr 1fr;
  }

  .period-filter button {
    grid-column: 1 / -1;
  }

  .status-banner {
    align-items: flex-start;
    flex-direction: column;
  }

  .status-banner button {
    margin-left: 0;
  }
}
</style>
