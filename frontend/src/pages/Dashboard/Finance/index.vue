<template>
  <section class="finance-page dashboard-page" :class="{ 'is-refreshing': isLoading && hasLoaded }">
    <header class="page-header">
      <div>
        <p class="eyebrow">Финансовый контроль</p>
        <h1>Финансы и выплаты</h1>
        <p class="page-subtitle">
          Сводные отчёты Wildberries, текущий баланс и автоматическая сверка с загруженной детализацией.
        </p>
      </div>
      <div class="period-controls">
        <label>
          <span>С</span>
          <input v-model="startDate" type="date" />
        </label>
        <label>
          <span>По</span>
          <input v-model="endDate" type="date" />
        </label>
        <button type="button" :disabled="isLoading" @click="loadData">
          {{ isLoading ? 'Обновляем…' : 'Применить' }}
        </button>
      </div>
    </header>

    <DashboardState v-if="isLoading && !hasLoaded" kind="loading" />

    <DashboardState
      v-if="errorMessage"
      kind="error"
      title="Не удалось загрузить финансы"
      :message="errorMessage"
      action-label="Повторить"
      @retry="loadData"
    />

    <div v-if="!errorMessage && (!isLoading || hasLoaded)" class="method-note">
      <strong>Источник истины по выплате — итог отчёта WB.</strong>
      <span>
        Мы не восстанавливаем «Итого к оплате» собственной формулой: сравниваем одноимённые поля сводного отчёта с детализацией и отдельно показываем расхождения.
      </span>
    </div>

    <div v-if="!errorMessage && (!isLoading || hasLoaded)" class="kpi-grid" aria-label="Сводка финансов">
      <article class="kpi-card kpi-card--accent">
        <span>Итого к оплате WB</span>
        <strong>{{ money(summary.bank_payment) }}</strong>
        <small>{{ number(summary.report_count) }} отчётов в выбранном периоде</small>
      </article>
      <article class="kpi-card">
        <span>К перечислению за товар</span>
        <strong>{{ money(summary.for_pay) }}</strong>
        <small>до прочих строк сводного отчёта</small>
      </article>
      <article class="kpi-card">
        <span>Логистика + хранение</span>
        <strong>{{ money(logisticsAndStorage) }}</strong>
        <small>логистика, хранение и приёмка</small>
      </article>
      <article class="kpi-card">
        <span>Доступно к выводу</span>
        <strong>{{ summary.for_withdraw == null ? '—' : money(summary.for_withdraw, summary.balance_currency) }}</strong>
        <small>{{ balanceCaption }}</small>
      </article>
      <article class="kpi-card" :class="{ 'kpi-card--warning': summary.mismatch_reports > 0 }">
        <span>Требуют проверки</span>
        <strong>{{ number(summary.mismatch_reports) }}</strong>
        <small>{{ number(summary.not_synced_reports) }} отчётов без детализации</small>
      </article>
    </div>

    <section v-if="!errorMessage && (!isLoading || hasLoaded)" class="balance-card">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Баланс WB</p>
          <h2>По кабинетам</h2>
        </div>
        <span class="section-meta">последний полученный balance widget</span>
      </div>

      <div v-if="!balances.length" class="empty-state empty-state--compact">
        <strong>Баланс ещё не синхронизирован.</strong>
        <span>Нужен токен WB с доступом к категории «Финансы».</span>
      </div>
      <div v-else class="balance-grid">
        <article v-for="balance in balances" :key="balance.token_id" class="balance-item">
          <div>
            <strong>{{ balance.account_label }}</strong>
            <span>{{ dateTime(balance.observed_at) }}</span>
          </div>
          <dl>
            <div>
              <dt>Текущий баланс</dt>
              <dd>{{ money(balance.current, balance.currency) }}</dd>
            </div>
            <div>
              <dt>Доступно к выводу</dt>
              <dd>{{ money(balance.for_withdraw, balance.currency) }}</dd>
            </div>
          </dl>
        </article>
      </div>
    </section>

    <section v-if="!errorMessage && (!isLoading || hasLoaded)" class="reports-card">
      <div class="section-heading section-heading--controls">
        <div>
          <p class="eyebrow">Отчёты реализации</p>
          <h2>Сверка summary ↔ detail</h2>
        </div>
        <select v-model="statusFilter" aria-label="Фильтр статуса сверки">
          <option value="all">Все статусы</option>
          <option value="mismatch">Требуют проверки</option>
          <option value="not_synced">Нет детализации</option>
          <option value="matched">Сверены</option>
        </select>
      </div>

      <div v-if="isLoading && !hasLoaded" class="empty-state">
        <strong>Загружаем финансовые отчёты…</strong>
        <span>Сопоставляем канонический summary WB с детальными строками Finance.</span>
      </div>
      <div v-else-if="!reports.length" class="empty-state">
        <strong>Отчётов за период пока нет.</strong>
        <span>Измените период или дождитесь завершения Finance-синхронизации.</span>
      </div>
      <div v-else-if="!filteredReports.length" class="empty-state">
        <strong>Нет отчётов с таким статусом.</strong>
        <span>Измените фильтр сверки.</span>
      </div>

      <div v-else class="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>Период</th>
              <th>Кабинет</th>
              <th class="number-cell">Продажа</th>
              <th class="number-cell">За товар</th>
              <th class="number-cell">Логистика</th>
              <th class="number-cell">Хранение</th>
              <th class="number-cell">Удержания</th>
              <th class="number-cell">Штрафы</th>
              <th class="number-cell">Итого WB</th>
              <th>Сверка</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="report in filteredReports" :key="`${report.token_id}:${report.report_id}`">
              <td>
                <div class="period-cell">
                  <strong>{{ shortDate(report.date_from) }} — {{ shortDate(report.date_to) }}</strong>
                  <span>№ {{ report.report_id }}</span>
                </div>
              </td>
              <td>{{ report.account_label }}</td>
              <td class="number-cell">{{ money(report.retail_amount, report.currency) }}</td>
              <td class="number-cell">{{ money(report.for_pay, report.currency) }}</td>
              <td class="number-cell">{{ money(report.delivery, report.currency) }}</td>
              <td class="number-cell">{{ money(report.storage, report.currency) }}</td>
              <td class="number-cell">{{ money(report.deduction, report.currency) }}</td>
              <td class="number-cell">{{ money(report.penalty, report.currency) }}</td>
              <td class="number-cell total-cell">{{ money(report.bank_payment, report.currency) }}</td>
              <td>
                <span class="status-pill" :class="statusClass(report.reconciliation_status)">
                  {{ statusLabel(report.reconciliation_status) }}
                </span>
                <small v-if="report.reconciliation_status === 'mismatch'" class="discrepancy">
                  max Δ {{ money(maxDiscrepancy(report), report.currency) }}
                </small>
                <small v-else-if="report.detail" class="detail-count">
                  {{ number(report.detail.row_count) }} строк
                </small>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import FinanceService from '@/API/Dashboard/FinanceService.js'
import DashboardState from '@/components/DashboardState.vue'
import { finiteOrZero, formatFiniteNumber, toFiniteNumber } from '@/utils/safeNumber'

const iso = (date) => date.toISOString().slice(0, 10)
const today = new Date()
const ninetyDaysAgo = new Date(today)
ninetyDaysAgo.setDate(today.getDate() - 89)

const startDate = ref(iso(ninetyDaysAgo))
const endDate = ref(iso(today))
const isLoading = ref(false)
const hasLoaded = ref(false)
const errorMessage = ref('')
const statusFilter = ref('all')
const reports = ref([])
const balances = ref([])
const summary = ref({
  report_count: 0,
  retail_amount: 0,
  for_pay: 0,
  delivery: 0,
  storage: 0,
  acceptance: 0,
  deduction: 0,
  penalty: 0,
  additional_payment: 0,
  bank_payment: 0,
  matched_reports: 0,
  mismatch_reports: 0,
  not_synced_reports: 0,
  balance_current: null,
  for_withdraw: null,
  balance_currency: null,
})

const filteredReports = computed(() => {
  if (statusFilter.value === 'all') return reports.value
  return reports.value.filter((report) => report.reconciliation_status === statusFilter.value)
})

const logisticsAndStorage = computed(() =>
  finiteOrZero(summary.value.delivery) +
  finiteOrZero(summary.value.storage) +
  finiteOrZero(summary.value.acceptance)
)

const balanceCaption = computed(() => {
  if (!balances.value.length) return 'баланс ещё не получен'
  if (summary.value.for_withdraw == null) return 'несколько валют — смотрите по кабинетам'
  return `${balances.value.length} кабинет(а)`
})

const number = (value) => formatFiniteNumber(value, {
  maximumFractionDigits: 0,
  fallback: '0',
})

const money = (value, currency = 'RUB') => {
  const numeric = toFiniteNumber(value)
  if (numeric === null) return '—'
  const symbol = !currency || currency === 'RUB' ? '₽' : currency
  return `${formatFiniteNumber(numeric, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  })} ${symbol}`
}

const shortDate = (value) => {
  if (!value) return '—'
  return new Intl.DateTimeFormat('ru-RU', { day: '2-digit', month: '2-digit', year: '2-digit' }).format(new Date(`${value}T00:00:00`))
}

const dateTime = (value) => {
  if (!value) return '—'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return '—'
  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit',
  }).format(parsed)
}

const statusLabel = (status) => ({
  matched: 'сверено',
  mismatch: 'расхождение',
  not_synced: 'нет детализации',
}[status] || status)

const statusClass = (status) => ({
  'status-pill--ok': status === 'matched',
  'status-pill--warning': status === 'mismatch',
  'status-pill--muted': status === 'not_synced',
})

const maxDiscrepancy = (report) => {
  const values = Object.values(report.discrepancies || {}).map((value) => Math.abs(finiteOrZero(value)))
  return values.length ? Math.max(...values) : 0
}

const loadData = async () => {
  if (!startDate.value || !endDate.value || startDate.value > endDate.value) {
    errorMessage.value = 'Проверьте выбранный период'
    return
  }

  isLoading.value = true
  errorMessage.value = ''
  try {
    const response = await FinanceService.get_finance({
      start_date: startDate.value,
      end_date: endDate.value,
    })
    const result = response.data
    if (result?.status === 'error') {
      errorMessage.value = result.error?.message || 'Не удалось загрузить финансовые данные'
      return
    }
    const data = result?.data || {}
    summary.value = { ...summary.value, ...(data.summary || {}) }
    balances.value = data.balances || []
    reports.value = data.reports || []
  } catch (error) {
    errorMessage.value = error.response?.data?.error?.message || 'Ошибка загрузки финансовых данных'
  } finally {
    hasLoaded.value = true
    isLoading.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.finance-page {
  width: min(100% - 32px, var(--content-width));
  margin: 0 auto;
  padding: 28px 0 48px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.page-header,
.period-controls,
.method-note,
.status-banner,
.section-heading,
.balance-grid,
.balance-item dl {
  display: flex;
}

.page-header {
  justify-content: space-between;
  align-items: flex-start;
  gap: 24px;
}

.eyebrow {
  margin: 0 0 5px;
  color: #6259d9;
  font-size: 11px;
  font-weight: 750;
  letter-spacing: .09em;
  text-transform: uppercase;
}

h1, h2, p { margin-top: 0; }
h1 { margin: 7px 0 8px; font-size: clamp(26px, 3vw, 36px); letter-spacing: -.035em; }
h2 { margin-bottom: 0; font-size: 19px; }
.page-subtitle { max-width: 720px; margin-bottom: 0; color: var(--text-muted); font-size: 14px; }

.period-controls { align-items: flex-end; gap: 8px; }
.period-controls label { display: flex; flex-direction: column; gap: 5px; color: var(--text-subtle); font-size: 11px; }
.period-controls input,
.period-controls button,
.section-heading select,
.status-banner button {
  min-height: 40px;
  padding: 8px 11px;
  border: 1px solid var(--border-color);
  border-radius: 9px;
  background: var(--card-bg-elevated);
  color: var(--text-color);
}
.period-controls button,
.status-banner button { cursor: pointer; }
.period-controls button:disabled { opacity: .55; cursor: default; }

.method-note,
.status-banner {
  padding: 13px 15px;
  align-items: center;
  gap: 10px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  background: var(--card-bg);
  color: var(--text-muted);
  font-size: 13px;
}
.method-note { flex-wrap: wrap; align-items: baseline; }
.method-note strong, .status-banner strong { color: var(--text-color); }
.status-banner { justify-content: space-between; }
.status-banner > div { display: flex; flex-direction: column; gap: 2px; }
.status-banner--error { border-color: rgba(244, 63, 94, .35); }

.kpi-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px; }
.kpi-card,
.balance-card,
.reports-card { border: 1px solid var(--border-color); background: var(--card-bg); box-shadow: var(--shadow-sm); }
.kpi-card { min-height: 116px; padding: 15px; display: flex; flex-direction: column; border-radius: var(--radius); }
.kpi-card > span { color: var(--text-muted); font-size: 12px; }
.kpi-card strong { margin-top: 8px; font-size: 23px; letter-spacing: -.03em; }
.kpi-card small { margin-top: auto; padding-top: 8px; color: var(--text-subtle); font-size: 11px; line-height: 1.35; }
.kpi-card--accent { border-color: rgba(124, 58, 237, .3); }
.kpi-card--accent strong { color: #5b52d6; }
.kpi-card--warning { border-color: rgba(245, 158, 11, .35); }
.kpi-card--warning strong { color: #a66b08; }

.balance-card,
.reports-card { overflow: hidden; border-radius: var(--radius); }
.section-heading { padding: 17px 18px; align-items: center; justify-content: space-between; gap: 16px; border-bottom: 1px solid var(--border-color); }
.section-heading--controls { align-items: flex-end; }
.section-meta { color: var(--text-subtle); font-size: 11px; }

.balance-grid { padding: 14px; gap: 10px; flex-wrap: wrap; }
.balance-item { flex: 1 1 320px; padding: 14px; border: 1px solid var(--border-color); border-radius: 10px; background: var(--light-bg); }
.balance-item > div { display: flex; flex-direction: column; gap: 3px; }
.balance-item > div span { color: var(--text-subtle); font-size: 11px; }
.balance-item dl { margin: 14px 0 0; gap: 24px; }
.balance-item dl div { display: flex; flex-direction: column; gap: 3px; }
.balance-item dt { color: var(--text-muted); font-size: 11px; }
.balance-item dd { margin: 0; font-weight: 700; }

.table-wrapper { overflow-x: auto; }
table { width: 100%; min-width: 1100px; border-collapse: collapse; }
th, td { padding: 12px 13px; border-bottom: 1px solid var(--border-color); text-align: left; font-size: 12px; vertical-align: middle; }
th { color: var(--text-subtle); font-size: 10px; font-weight: 700; letter-spacing: .04em; text-transform: uppercase; }
tbody tr:last-child td { border-bottom: 0; }
.number-cell { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.total-cell { color: #5b52d6; font-weight: 700; }
.period-cell { display: flex; flex-direction: column; gap: 3px; white-space: nowrap; }
.period-cell span { color: var(--text-subtle); font-size: 10px; }

.status-pill { display: inline-flex; padding: 4px 7px; border: 1px solid var(--border-color); border-radius: 999px; color: var(--text-muted); font-size: 10px; white-space: nowrap; }
.status-pill--ok { border-color: rgba(34, 197, 94, .28); color: #16805f; background: rgba(22, 128, 95, .08); }
.status-pill--warning { border-color: rgba(245, 158, 11, .3); color: #a66b08; background: rgba(166, 107, 8, .08); }
.status-pill--muted { color: var(--text-subtle); }
.discrepancy,
.detail-count { display: block; margin-top: 5px; color: var(--text-subtle); font-size: 10px; white-space: nowrap; }

.empty-state { padding: 44px 20px; display: flex; flex-direction: column; align-items: center; gap: 5px; color: var(--text-muted); text-align: center; }
.empty-state strong { color: var(--text-color); }
.empty-state--compact { padding: 24px 18px; align-items: flex-start; text-align: left; }

@media (max-width: 1100px) {
  .kpi-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .page-header { flex-direction: column; }
}

@media (max-width: 720px) {
  .finance-page { width: min(100% - 20px, var(--content-width)); padding-top: 20px; }
  .kpi-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .period-controls { width: 100%; flex-wrap: wrap; }
  .period-controls label { flex: 1 1 130px; }
  .period-controls input, .period-controls button { width: 100%; }
  .section-heading--controls { align-items: stretch; flex-direction: column; }
  .section-heading select { width: 100%; }
}

@media (max-width: 460px) {
  .kpi-grid { grid-template-columns: 1fr; }
  .balance-item dl { flex-direction: column; gap: 10px; }
}
</style>
