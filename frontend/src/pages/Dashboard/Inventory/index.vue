<template>
  <section class="inventory-page dashboard-page" :class="{ 'is-refreshing': isLoading && hasLoadedOnce }">
    <header class="page-header">
      <div>
        <p class="eyebrow">Запасы</p>
        <h1>Остатки и пополнение</h1>
        <p class="page-subtitle">
          Риск дефицита и рекомендация поставки по фактическому FBO-остатку и заказам за 30 завершённых дней.
        </p>
      </div>
      <button class="refresh-button" type="button" :disabled="isLoading" @click="loadData">
        {{ isLoading ? 'Обновляем…' : 'Обновить' }}
      </button>
    </header>

    <DashboardState v-if="isLoading && !hasLoadedOnce" kind="loading" />

    <DashboardState
      v-if="errorMessage"
      kind="error"
      title="Не удалось загрузить остатки"
      :message="errorMessage"
      action-label="Повторить"
      @retry="loadData"
    />

    <div v-if="period && !errorMessage && (!isLoading || hasLoadedOnce)" class="method-note">
      <strong>{{ period.start_date }} — {{ period.end_date }}</strong>
      <span>
        Скорость = заказы / {{ period.lookback_days }} дней · критично &lt; {{ period.critical_days }} дней · цель {{ period.target_days }} дней.
        Товары в пути показаны отдельно и не увеличивают FBO-покрытие.
      </span>
    </div>

    <div v-if="!errorMessage && (!isLoading || hasLoadedOnce)" class="kpi-grid" aria-label="Сводка по остаткам">
      <article class="kpi-card">
        <span>Остаток FBO</span>
        <strong>{{ formatNumber(summary.stock_units) }}</strong>
        <small>единиц на складах WB</small>
      </article>
      <article class="kpi-card kpi-card--danger">
        <span>Критический риск</span>
        <strong>{{ formatNumber(summary.critical_products) }}</strong>
        <small>нет товара или запас менее 14 дней</small>
      </article>
      <article class="kpi-card kpi-card--warning">
        <span>Нужно пополнить</span>
        <strong>{{ formatNumber(summary.replenish_products) }}</strong>
        <small>SKU ниже целевого запаса 30 дней</small>
      </article>
      <article class="kpi-card">
        <span>Рекомендовано поставить</span>
        <strong>{{ formatNumber(summary.recommended_supply_units) }}</strong>
        <small>единиц до целевого запаса</small>
      </article>
      <article class="kpi-card">
        <span>В пути к клиенту</span>
        <strong>{{ formatNumber(summary.in_way_to_client) }}</strong>
        <small>информационно, вне покрытия</small>
      </article>
      <article class="kpi-card">
        <span>Без спроса</span>
        <strong>{{ formatNumber(summary.no_demand_products) }}</strong>
        <small>есть остаток, но нет заказов за 30 дней</small>
      </article>
    </div>

    <section v-if="!errorMessage && (!isLoading || hasLoadedOnce)" class="table-card">
      <div class="table-heading">
        <div>
          <p class="eyebrow">Приоритет пополнения</p>
          <h2>Товары</h2>
        </div>
        <div class="table-controls">
          <input v-model.trim="searchQuery" type="search" placeholder="Название или nmId" aria-label="Поиск товара" />
          <select v-model="statusFilter" aria-label="Фильтр по статусу">
            <option value="all">Все статусы</option>
            <option value="risk">Требуют пополнения</option>
            <option value="critical">Только критические</option>
            <option value="healthy">Запас достаточен</option>
            <option value="no_demand">Без спроса</option>
          </select>
        </div>
      </div>

      <div v-if="isLoading && !hasLoadedOnce" class="empty-state">
        <strong>Считаем покрытие запасом…</strong>
        <span>Объединяем текущий FBO-остаток и заказы завершённых 30 дней.</span>
      </div>

      <div v-else-if="!items.length" class="empty-state">
        <strong>Нет данных об остатках.</strong>
        <span>После успешной синхронизации WB здесь появятся позиции и рекомендации.</span>
      </div>

      <div v-else-if="!filteredItems.length" class="empty-state">
        <strong>Ничего не найдено.</strong>
        <span>Измените поиск или фильтр статуса.</span>
      </div>

      <div v-else class="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>Товар</th>
              <th>Статус</th>
              <th class="number-cell">FBO</th>
              <th class="number-cell">В пути → клиенту</th>
              <th class="number-cell">В пути ← от клиента</th>
              <th class="number-cell">Заказов / 30 дн.</th>
              <th class="number-cell">Заказов / день</th>
              <th class="number-cell">Покрытие, дней</th>
              <th class="number-cell supply-column">Поставить</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in filteredItems" :key="item.nm_id" :class="rowClass(item.status)">
              <td>
                <div class="product-cell">
                  <strong>{{ item.product_name || 'Без названия' }}</strong>
                  <span>nmId {{ item.nm_id }}</span>
                </div>
              </td>
              <td>
                <span class="status-pill" :class="`status-pill--${item.status}`">
                  {{ statusLabel(item.status) }}
                </span>
              </td>
              <td class="number-cell">{{ formatNumber(item.stock_units) }}</td>
              <td class="number-cell muted-cell">{{ formatNumber(item.in_way_to_client) }}</td>
              <td class="number-cell muted-cell">{{ formatNumber(item.in_way_from_client) }}</td>
              <td class="number-cell">{{ formatNumber(item.orders_30d) }}</td>
              <td class="number-cell">{{ formatDecimal(item.orders_per_day) }}</td>
              <td class="number-cell">
                <strong v-if="item.coverage_days != null">{{ formatDecimal(item.coverage_days) }}</strong>
                <span v-else class="muted-cell">—</span>
              </td>
              <td class="number-cell supply-column">
                <strong v-if="item.recommended_supply_units > 0" class="supply-value">
                  +{{ formatNumber(item.recommended_supply_units) }}
                </strong>
                <span v-else-if="item.excess_units > 0" class="excess-value">
                  запас +{{ formatNumber(item.excess_units) }}
                </span>
                <span v-else class="muted-cell">0</span>
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
import InventoryService from '@/API/Dashboard/InventoryService.js'
import DashboardState from '@/components/DashboardState.vue'

const isLoading = ref(false)
const hasLoadedOnce = ref(false)
const errorMessage = ref('')
const items = ref([])
const summary = ref({
  products: 0,
  stock_units: 0,
  in_way_to_client: 0,
  in_way_from_client: 0,
  critical_products: 0,
  replenish_products: 0,
  no_demand_products: 0,
  recommended_supply_units: 0,
})
const period = ref(null)
const searchQuery = ref('')
const statusFilter = ref('all')

const riskStatuses = new Set(['out_of_stock', 'critical', 'replenish'])
const criticalStatuses = new Set(['out_of_stock', 'critical'])

const filteredItems = computed(() => {
  const query = searchQuery.value.toLowerCase()
  return items.value.filter((item) => {
    const matchesSearch = !query ||
      String(item.nm_id).includes(query) ||
      (item.product_name || '').toLowerCase().includes(query)

    let matchesStatus = true
    if (statusFilter.value === 'risk') matchesStatus = riskStatuses.has(item.status)
    if (statusFilter.value === 'critical') matchesStatus = criticalStatuses.has(item.status)
    if (statusFilter.value === 'healthy') matchesStatus = item.status === 'healthy'
    if (statusFilter.value === 'no_demand') matchesStatus = item.status === 'no_demand'

    return matchesSearch && matchesStatus
  })
})

const formatNumber = (value) => new Intl.NumberFormat('ru-RU', {
  maximumFractionDigits: 0,
}).format(Number(value || 0))

const formatDecimal = (value) => new Intl.NumberFormat('ru-RU', {
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
}).format(Number(value || 0))

const statusLabel = (status) => ({
  out_of_stock: 'Нет остатка',
  critical: 'Критично',
  replenish: 'Пополнить',
  healthy: 'Достаточно',
  no_demand: 'Нет спроса',
  no_stock_no_demand: 'Нет движения',
}[status] || status)

const rowClass = (status) => ({
  'row--critical': criticalStatuses.has(status),
  'row--replenish': status === 'replenish',
})

const loadData = async () => {
  isLoading.value = true
  errorMessage.value = ''

  try {
    const response = await InventoryService.get_inventory()
    const result = response.data

    if (result?.status === 'error') {
      errorMessage.value = result.error?.message || 'Не удалось загрузить данные'
      return
    }

    const data = result?.data || {}
    items.value = data.items || []
    summary.value = { ...summary.value, ...(data.summary || {}) }
    period.value = data.period || null
  } catch (error) {
    errorMessage.value = error.response?.data?.error?.message || 'Ошибка загрузки данных об остатках'
  } finally {
    hasLoadedOnce.value = true
    isLoading.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.inventory-page {
  width: min(100% - 32px, var(--content-width));
  margin: 0 auto;
  padding: 28px 0 48px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
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

h1,
h2,
p {
  margin-top: 0;
}

h1 {
  margin-bottom: 8px;
  font-size: clamp(26px, 3vw, 36px);
  letter-spacing: -.035em;
}

h2 {
  margin-bottom: 0;
  font-size: 19px;
}

.page-subtitle {
  max-width: 760px;
  margin-bottom: 0;
  color: var(--text-muted);
  font-size: 14px;
}

.refresh-button,
.status-banner button {
  min-height: 40px;
  padding: 9px 14px;
  border: 1px solid var(--border-color);
  border-radius: 9px;
  background: var(--card-bg-elevated);
  color: var(--text-color);
  cursor: pointer;
}

.refresh-button:hover,
.status-banner button:hover {
  background: var(--hover-bg);
}

.refresh-button:disabled {
  opacity: .55;
  cursor: default;
}

.status-banner,
.method-note {
  padding: 13px 15px;
  display: flex;
  align-items: center;
  gap: 12px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  background: var(--card-bg);
}

.status-banner {
  justify-content: space-between;
}

.status-banner > div,
.method-note {
  color: var(--text-muted);
  font-size: 13px;
}

.status-banner strong,
.method-note strong {
  color: var(--text-color);
}

.status-banner > div {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.status-banner--error {
  border-color: rgba(244, 63, 94, .35);
}

.method-note {
  align-items: baseline;
  flex-wrap: wrap;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 10px;
}

.kpi-card,
.table-card {
  border: 1px solid var(--border-color);
  background: var(--card-bg);
  box-shadow: var(--shadow-sm);
}

.kpi-card {
  min-height: 116px;
  padding: 15px;
  display: flex;
  flex-direction: column;
  border-radius: var(--radius);
}

.kpi-card > span {
  color: var(--text-muted);
  font-size: 12px;
}

.kpi-card strong {
  margin-top: 8px;
  font-size: 24px;
  letter-spacing: -.03em;
}

.kpi-card small {
  margin-top: auto;
  padding-top: 8px;
  color: var(--text-subtle);
  font-size: 11px;
  line-height: 1.35;
}

.kpi-card--danger {
  border-color: rgba(244, 63, 94, .28);
}

.kpi-card--danger strong {
  color: #c83b55;
}

.kpi-card--warning {
  border-color: rgba(245, 158, 11, .28);
}

.kpi-card--warning strong {
  color: #a66b08;
}

.table-card {
  overflow: hidden;
  border-radius: var(--radius);
}

.table-heading {
  padding: 17px 18px;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
  border-bottom: 1px solid var(--border-color);
}

.table-controls {
  display: flex;
  gap: 8px;
}

.table-controls input,
.table-controls select {
  min-height: 38px;
  padding: 8px 10px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--light-bg);
  color: var(--text-color);
  font: inherit;
}

.table-controls input {
  min-width: 220px;
}

.table-controls input:focus,
.table-controls select:focus {
  outline: 2px solid rgba(124, 58, 237, .35);
  border-color: var(--secondary-color);
}

.table-wrapper {
  overflow-x: auto;
}

table {
  width: 100%;
  min-width: 1080px;
  border-collapse: collapse;
}

th,
td {
  padding: 12px 13px;
  border-bottom: 1px solid var(--border-color);
  text-align: left;
  font-size: 12px;
}

th {
  position: sticky;
  top: 0;
  z-index: 1;
  background: var(--medium-bg);
  color: var(--text-muted);
  font-weight: 650;
  white-space: nowrap;
}

tbody tr:last-child td {
  border-bottom: 0;
}

tbody tr:hover td {
  background: rgba(148, 163, 184, .035);
}

.row--critical td:first-child {
  box-shadow: inset 3px 0 0 #d84c64;
}

.row--replenish td:first-child {
  box-shadow: inset 3px 0 0 #c98713;
}

.product-cell {
  min-width: 190px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.product-cell strong {
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
}

.product-cell span,
.muted-cell {
  color: var(--text-subtle);
}

.number-cell {
  text-align: right;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.supply-column {
  background: rgba(124, 58, 237, .035);
}

.supply-value {
  color: #5b52d6;
}

.excess-value {
  color: #16805f;
  font-size: 11px;
}

.status-pill {
  display: inline-flex;
  padding: 4px 7px;
  border-radius: 999px;
  border: 1px solid var(--border-color);
  color: var(--text-muted);
  font-size: 10px;
  font-weight: 700;
  white-space: nowrap;
}

.status-pill--out_of_stock,
.status-pill--critical {
  border-color: rgba(244, 63, 94, .35);
  background: rgba(200, 59, 85, .08);
  color: #c83b55;
}

.status-pill--replenish {
  border-color: rgba(245, 158, 11, .35);
  background: rgba(166, 107, 8, .08);
  color: #a66b08;
}

.status-pill--healthy {
  border-color: rgba(34, 197, 94, .3);
  background: rgba(22, 128, 95, .07);
  color: #16805f;
}

.status-pill--no_demand,
.status-pill--no_stock_no_demand {
  color: var(--text-subtle);
}

.empty-state {
  min-height: 190px;
  padding: 32px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 5px;
  color: var(--text-muted);
  text-align: center;
}

.empty-state strong {
  color: var(--text-color);
}

@media (max-width: 1200px) {
  .kpi-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (max-width: 760px) {
  .inventory-page {
    width: min(100% - 20px, var(--content-width));
    padding-top: 20px;
  }

  .page-header,
  .table-heading {
    align-items: stretch;
    flex-direction: column;
  }

  .refresh-button {
    width: 100%;
  }

  .kpi-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .table-controls {
    flex-direction: column;
  }

  .table-controls input,
  .table-controls select {
    width: 100%;
    min-width: 0;
  }
}

@media (max-width: 460px) {
  .kpi-grid {
    grid-template-columns: 1fr;
  }
}
</style>
