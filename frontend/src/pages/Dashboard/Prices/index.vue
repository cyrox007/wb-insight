<template>
  <section class="prices-page">
    <header class="page-header">
      <div>
        <div class="title-line">
          <p class="eyebrow">Ценообразование</p>
          <span class="read-only-badge">только чтение</span>
        </div>
        <h1>Цены и скидки</h1>
        <p class="page-subtitle">
          Текущие цены Wildberries и история фактических изменений. WB Insight ничего не меняет в кабинете продавца на этом экране.
        </p>
      </div>
      <button class="refresh-button" type="button" :disabled="isLoading" @click="loadData">
        {{ isLoading ? 'Обновляем…' : 'Обновить' }}
      </button>
    </header>

    <div v-if="errorMessage" class="status-banner status-banner--error" role="alert">
      <div>
        <strong>Не удалось загрузить цены.</strong>
        <span>{{ errorMessage }}</span>
      </div>
      <button type="button" @click="loadData">Повторить</button>
    </div>

    <div class="method-note">
      <strong>Источник: WB Prices & Discounts API.</strong>
      <span>
        История создаётся только при реальном изменении цены или скидки; первая синхронизация становится исходной точкой и не считается изменением.
      </span>
    </div>

    <div class="kpi-grid" aria-label="Сводка цен">
      <article class="kpi-card">
        <span>Товаров</span>
        <strong>{{ formatNumber(summary.products) }}</strong>
        <small>{{ formatNumber(summary.sizes) }} цен по размерам</small>
      </article>
      <article class="kpi-card kpi-card--accent">
        <span>Изменились за 30 дней</span>
        <strong>{{ formatNumber(summary.changed_products_30d) }}</strong>
        <small>{{ formatNumber(summary.changes_30d) }} событий изменения</small>
      </article>
      <article class="kpi-card">
        <span>Средняя скидка</span>
        <strong>{{ formatPercent(summary.avg_discount) }}</strong>
        <small>среднее по текущим товарам</small>
      </article>
      <article class="kpi-card">
        <span>WB Club</span>
        <strong>{{ formatNumber(summary.club_price_products) }}</strong>
        <small>товаров с клубной ценой</small>
      </article>
      <article class="kpi-card kpi-card--warning">
        <span>Низкая оборачиваемость WB</span>
        <strong>{{ formatNumber(summary.bad_turnover_products) }}</strong>
        <small>флаг isBadTurnover от Wildberries</small>
      </article>
    </div>

    <section class="table-card">
      <div class="section-heading section-heading--controls">
        <div>
          <p class="eyebrow">Текущее состояние</p>
          <h2>Товары</h2>
        </div>
        <div class="table-controls">
          <input v-model.trim="searchQuery" type="search" placeholder="Название, артикул или nmId" aria-label="Поиск товара" />
          <select v-model="productFilter" aria-label="Фильтр товаров">
            <option value="all">Все товары</option>
            <option value="changed">Менялись за 30 дней</option>
            <option value="club">Есть WB Club</option>
            <option value="bad-turnover">Низкая оборачиваемость</option>
          </select>
        </div>
      </div>

      <div v-if="isLoading && !hasLoadedOnce" class="empty-state">
        <strong>Загружаем цены…</strong>
        <span>Собираем текущий snapshot и историю изменений.</span>
      </div>
      <div v-else-if="!products.length" class="empty-state">
        <strong>Цена ещё не синхронизирована.</strong>
        <span>Для этого кабинета нужен токен WB с доступом к категории «Цены и скидки».</span>
      </div>
      <div v-else-if="!filteredProducts.length" class="empty-state">
        <strong>Ничего не найдено.</strong>
        <span>Измените поиск или фильтр.</span>
      </div>

      <div v-else class="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>Товар</th>
              <th>Кабинет</th>
              <th class="number-cell">Базовая цена</th>
              <th class="number-cell">Цена со скидкой</th>
              <th class="number-cell">Скидка</th>
              <th class="number-cell">WB Club</th>
              <th class="number-cell">Размеров</th>
              <th class="number-cell">Изменений / 30 дн.</th>
              <th>Состояние</th>
              <th>Синхронизировано</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in filteredProducts" :key="`${item.token_id}:${item.nm_id}`">
              <td>
                <div class="product-cell">
                  <strong>{{ item.product_name || item.vendor_code || 'Без названия' }}</strong>
                  <span>nmId {{ item.nm_id }}<template v-if="item.vendor_code"> · {{ item.vendor_code }}</template></span>
                </div>
              </td>
              <td class="muted-cell">{{ item.account_label }}</td>
              <td class="number-cell">{{ formatPriceRange(item.base_price, item.currency) }}</td>
              <td class="number-cell price-cell">{{ formatPriceRange(item.discounted_price, item.currency) }}</td>
              <td class="number-cell">{{ formatPercent(item.discount) }}</td>
              <td class="number-cell">{{ item.has_club_price ? formatPriceRange(item.club_discounted_price, item.currency) : '—' }}</td>
              <td class="number-cell">{{ formatNumber(item.size_count) }}</td>
              <td class="number-cell">
                <span :class="{ 'change-count': item.changes_30d > 0 }">{{ formatNumber(item.changes_30d) }}</span>
              </td>
              <td>
                <span v-if="item.is_bad_turnover" class="status-pill status-pill--warning">низкая оборачиваемость</span>
                <span v-else-if="item.changes_30d > 0" class="status-pill status-pill--changed">цена менялась</span>
                <span v-else class="status-pill">без изменений</span>
              </td>
              <td class="muted-cell">{{ formatDateTime(item.observed_at) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="history-card">
      <div class="section-heading">
        <div>
          <p class="eyebrow">История</p>
          <h2>Последние изменения</h2>
        </div>
        <span class="section-meta">30 дней · до 50 событий</span>
      </div>

      <div v-if="!recentChanges.length" class="empty-state empty-state--compact">
        <strong>Изменений пока нет.</strong>
        <span>После первого последующего изменения цены здесь появится сравнение «было → стало».</span>
      </div>

      <div v-else class="change-list">
        <article v-for="change in recentChanges" :key="changeKey(change)" class="change-row">
          <div class="change-product">
            <strong>{{ change.product_name || change.vendor_code || `nmId ${change.nm_id}` }}</strong>
            <span>
              {{ change.account_label }} · nmId {{ change.nm_id }}
              <template v-if="change.tech_size_name"> · размер {{ change.tech_size_name }}</template>
            </span>
          </div>

          <div class="change-values">
            <div>
              <span>Цена со скидкой</span>
              <strong>
                <s>{{ formatMoney(change.previous_discounted_price, change.currency) }}</s>
                <span class="arrow">→</span>
                {{ formatMoney(change.discounted_price, change.currency) }}
              </strong>
            </div>
            <div v-if="change.previous_discount !== change.discount">
              <span>Скидка</span>
              <strong>{{ formatPercent(change.previous_discount) }} <span class="arrow">→</span> {{ formatPercent(change.discount) }}</strong>
            </div>
          </div>

          <time :datetime="change.changed_at">{{ formatDateTime(change.changed_at) }}</time>
        </article>
      </div>
    </section>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import PriceService from '@/API/Dashboard/PriceService.js'

const isLoading = ref(false)
const hasLoadedOnce = ref(false)
const errorMessage = ref('')
const products = ref([])
const recentChanges = ref([])
const summary = ref({
  products: 0,
  sizes: 0,
  changes_30d: 0,
  changed_products_30d: 0,
  avg_discount: 0,
  club_price_products: 0,
  bad_turnover_products: 0,
})

const searchQuery = ref('')
const productFilter = ref('all')

const filteredProducts = computed(() => {
  const query = searchQuery.value.toLowerCase()
  return products.value.filter((item) => {
    const matchesSearch = !query ||
      String(item.nm_id).includes(query) ||
      (item.product_name || '').toLowerCase().includes(query) ||
      (item.vendor_code || '').toLowerCase().includes(query)

    let matchesFilter = true
    if (productFilter.value === 'changed') matchesFilter = item.changes_30d > 0
    if (productFilter.value === 'club') matchesFilter = item.has_club_price
    if (productFilter.value === 'bad-turnover') matchesFilter = item.is_bad_turnover
    return matchesSearch && matchesFilter
  })
})

const formatNumber = (value) => new Intl.NumberFormat('ru-RU', {
  maximumFractionDigits: 0,
}).format(Number(value || 0))

const formatPercent = (value) => `${new Intl.NumberFormat('ru-RU', {
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
}).format(Number(value || 0))}%`

const currencySymbol = (currency) => currency === 'RUB' || !currency ? '₽' : currency

const formatMoney = (value, currency) => {
  if (value == null) return '—'
  return `${new Intl.NumberFormat('ru-RU', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(Number(value))} ${currencySymbol(currency)}`
}

const formatPriceRange = (range, currency) => {
  if (!range || range.min == null) return '—'
  if (range.max == null || Number(range.min) === Number(range.max)) {
    return formatMoney(range.min, currency)
  }
  return `${formatMoney(range.min, currency)} – ${formatMoney(range.max, currency)}`
}

const formatDateTime = (value) => {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

const changeKey = (change) => [
  change.token_id,
  change.nm_id,
  change.size_id,
  change.changed_at,
].join(':')

const loadData = async () => {
  isLoading.value = true
  errorMessage.value = ''
  try {
    const response = await PriceService.get_prices()
    const result = response.data
    if (result?.status === 'error') {
      errorMessage.value = result.error?.message || 'Не удалось загрузить цены'
      return
    }

    const data = result?.data || {}
    products.value = data.products || []
    recentChanges.value = data.recent_changes || []
    summary.value = { ...summary.value, ...(data.summary || {}) }
  } catch (error) {
    errorMessage.value = error.response?.data?.error?.message || 'Ошибка загрузки цен и скидок'
  } finally {
    hasLoadedOnce.value = true
    isLoading.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.prices-page {
  width: min(100% - 32px, var(--content-width));
  margin: 0 auto;
  padding: 28px 0 48px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.page-header,
.section-heading,
.title-line,
.status-banner,
.method-note,
.table-controls,
.change-values {
  display: flex;
}

.page-header {
  justify-content: space-between;
  align-items: flex-start;
  gap: 24px;
}

.title-line {
  align-items: center;
  gap: 8px;
}

.eyebrow {
  margin: 0 0 5px;
  color: #6259d9;
  font-size: 11px;
  font-weight: 750;
  letter-spacing: .09em;
  text-transform: uppercase;
}

.title-line .eyebrow {
  margin-bottom: 0;
}

.read-only-badge {
  padding: 3px 7px;
  border: 1px solid rgba(148, 163, 184, .2);
  border-radius: 999px;
  color: var(--text-subtle);
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: .05em;
}

h1,
h2,
p {
  margin-top: 0;
}

h1 {
  margin: 7px 0 8px;
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
  align-items: center;
  gap: 10px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  background: var(--card-bg);
  color: var(--text-muted);
  font-size: 13px;
}

.status-banner {
  justify-content: space-between;
}

.status-banner > div {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.status-banner strong,
.method-note strong {
  color: var(--text-color);
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
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
}

.kpi-card,
.table-card,
.history-card {
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

.kpi-card--accent {
  border-color: rgba(124, 58, 237, .3);
}

.kpi-card--accent strong {
  color: #5b52d6;
}

.kpi-card--warning {
  border-color: rgba(245, 158, 11, .26);
}

.kpi-card--warning strong {
  color: #a66b08;
}

.table-card,
.history-card {
  overflow: hidden;
  border-radius: var(--radius);
}

.section-heading {
  padding: 17px 18px;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid var(--border-color);
}

.section-heading--controls {
  align-items: flex-end;
}

.section-meta {
  color: var(--text-subtle);
  font-size: 11px;
}

.table-controls {
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
  min-width: 250px;
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
  min-width: 1200px;
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

.product-cell,
.change-product,
.change-values > div {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.product-cell {
  min-width: 200px;
}

.product-cell strong {
  max-width: 270px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.product-cell span,
.change-product span,
.muted-cell {
  color: var(--text-subtle);
}

.number-cell {
  text-align: right;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.price-cell {
  color: #5148c7;
  font-weight: 650;
}

.change-count {
  display: inline-flex;
  min-width: 24px;
  justify-content: center;
  padding: 2px 6px;
  border-radius: 999px;
  background: rgba(99, 91, 255, .08);
  color: #5b52d6;
  font-weight: 700;
}

.status-pill {
  display: inline-flex;
  padding: 4px 7px;
  border: 1px solid var(--border-color);
  border-radius: 999px;
  color: var(--text-subtle);
  font-size: 10px;
  white-space: nowrap;
}

.status-pill--changed {
  border-color: rgba(124, 58, 237, .3);
  color: #5b52d6;
}

.status-pill--warning {
  border-color: rgba(245, 158, 11, .3);
  color: #a66b08;
}

.change-list {
  display: flex;
  flex-direction: column;
}

.change-row {
  padding: 14px 18px;
  display: grid;
  grid-template-columns: minmax(220px, 1.3fr) minmax(320px, 1fr) auto;
  align-items: center;
  gap: 20px;
  border-bottom: 1px solid var(--border-color);
}

.change-row:last-child {
  border-bottom: 0;
}

.change-product strong {
  font-size: 13px;
}

.change-product span,
.change-values span,
.change-row time {
  font-size: 11px;
}

.change-values {
  gap: 24px;
}

.change-values > div > span {
  color: var(--text-subtle);
}

.change-values strong {
  font-size: 12px;
  white-space: nowrap;
}

.change-values s {
  color: var(--text-muted);
  font-weight: 500;
}

.arrow {
  padding: 0 4px;
  color: var(--text-subtle);
}

.change-row time {
  color: var(--text-subtle);
  white-space: nowrap;
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

.empty-state--compact {
  min-height: 130px;
}

.empty-state strong {
  color: var(--text-color);
}

@media (max-width: 1100px) {
  .kpi-grid {
    grid-template-columns: repeat(3, 1fr);
  }

  .change-row {
    grid-template-columns: 1fr;
    gap: 10px;
  }
}

@media (max-width: 760px) {
  .prices-page {
    width: min(100% - 20px, var(--content-width));
    padding-top: 20px;
  }

  .page-header,
  .section-heading--controls {
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

  .change-values {
    flex-direction: column;
    gap: 8px;
  }
}

@media (max-width: 460px) {
  .kpi-grid {
    grid-template-columns: 1fr;
  }
}
</style>
