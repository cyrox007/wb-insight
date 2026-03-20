<template>
	<div class="dashboard-container">
		<!-- Сайдбар -->
		<aside class="dashboard-sidebar">
			<!-- Key Indicators -->
			<div class="sidebar-section">
				<h3 class="sidebar-title"><i class="fa fa-line-chart" aria-hidden="true"></i> Ключевые показатели</h3>
				<ul class="product-list">
					<li v-for="product in products" :key="product.id" class="product-item"
						:class="{ 'active': selectedProductId === product.id }" @click="selectProduct(product)">
						<div class="product-image">{{ product.name.substring(0, 2) }}</div>
						<div class="product-info">
							<div class="product-name">{{ product.name }}</div>
							<div class="product-stats">
								<span class="stat-badge sales">{{ product.sales }} продаж</span>
								<span class="stat-badge profit">{{ product.profit }} прибыль</span>
							</div>
						</div>
					</li>
				</ul>
			</div>

			<!-- Size Chart -->
			<div class="sidebar-section">
				<h3 class="sidebar-title"><i class="fa fa-ruler"></i> Размерная сетка</h3>
				<div class="size-chart-container">
					<table class="size-table">
						<thead>
							<tr>
								<th>Размер</th>
								<th>Кол-во</th>
								<th>В пути</th>
								<th>Доступно</th>
							</tr>
						</thead>
						<tbody>
							<tr v-for="size in sizeChart" :key="size.size">
								<td><span class="size-badge">{{ size.size }}</span></td>
								<td>{{ size.quantity }}</td>
								<td><span class="transit-badge">{{ size.inTransit }}</span></td>
								<td><span class="available-badge">{{ size.quantity - size.inTransit }}</span></td>
							</tr>
						</tbody>
					</table>
				</div>
			</div>

			<!-- Filters -->
			<div class="sidebar-section">
				<h3 class="sidebar-title"><i class="fa fa-filter"></i> Фильтры</h3>
				<div class="filter-group">
					<div v-for="filter in filters" :key="filter.key" class="filter-item"
						@click="toggleFilter(filter.key)">
						<div class="filter-checkbox" :class="{ checked: filter.checked }"></div>
						<span class="filter-label">{{ filter.label }}</span>
						<span class="filter-count" v-if="filter.count">({{ filter.count }})</span>
					</div>
				</div>

				<!-- Date Filter -->
				<div class="date-filter">
					<h4 class="filter-subtitle">Период</h4>
					<div class="date-inputs">
						<div class="date-input-group">
							<label>С</label>
							<input type="date" v-model="filterStartDate" class="date-picker">
						</div>
						<div class="date-input-group">
							<label>По</label>
							<input type="date" v-model="filterEndDate" class="date-picker">
						</div>
					</div>
					<button class="btn btn-sm btn-outline apply-filter-btn" @click="applyDateFilter">
						Применить
					</button>
				</div>
			</div>

			<!-- Quick Actions -->
			<div class="sidebar-section">
				<h3 class="sidebar-title"><i class="fa fa-bolt"></i> Быстрые действия</h3>
				<div class="quick-actions">
					<button class="quick-action-btn" @click="exportData">
						<i class="fa fa-file-export"></i>
						<span>Экспорт данных</span>
					</button>
					<button class="quick-action-btn" @click="generateReport">
						<i class="fa fa-chart-bar"></i>
						<span>Создать отчет</span>
					</button>
					<button class="quick-action-btn" @click="addProduct">
						<i class="fa fa-plus"></i>
						<span>Добавить товар</span>
					</button>
					<button class="quick-action-btn" @click="refreshData">
						<i class="fa fa-sync-alt"></i>
						<span>Обновить данные</span>
					</button>
				</div>
			</div>
		</aside>
		<!-- Основное содержимое дашборда -->
		<div class="main-dashboard-content">
			<!-- Dashboard Header -->
			<div class="dashboard-header">
				<h1 class="dashboard-title">Общие показатели по кабинету</h1>
				<div class="btn-group">
					<button class="btn btn-primary" @click="toggleMoreInfo">
						<i class="fa fa-info-circle"></i> Больше информации
					</button>
				</div>
			</div>

			<!-- Stats Grid -->
			<div class="stats-grid">
				<!-- Заказано на сумму -->
				<div class="stat-card primary">
					<div class="stat-title">Заказано на сумму</div>
					<div class="stat-value primary">
						{{ stats.ordered_amount?.value != null ? formatNumber(stats.ordered_amount.value) + ' ₽' : '—'
						}}
					</div>
					<div class="stat-change">
						{{ stats.ordered_amount?.change_percent != null
							? formatChange(stats.ordered_amount.change_percent) + ' за период'
							: 'Данные не синхронизированы' }}
					</div>
				</div>

				<!-- Единиц (заказано) -->
				<div class="stat-card primary">
					<div class="stat-title">Единиц</div>
					<div class="stat-value primary">
						{{ stats.ordered_units?.value != null ? formatNumber(stats.ordered_units.value) : '—' }}
					</div>
					<div class="stat-change">
						{{ stats.ordered_units?.change_percent != null
							? formatChange(stats.ordered_units.change_percent) + ' за период'
							: 'Данные не синхронизированы' }}
					</div>
				</div>

				<!-- Выручка -->
				<div class="stat-card success">
					<div class="stat-title">Выручка</div>
					<div class="stat-value success">
						{{ stats.revenue?.value != null ? formatNumber(stats.revenue.value) + ' ₽' : '—' }}
					</div>
					<div class="stat-change">
						{{ stats.revenue?.change_percent != null
							? formatChange(stats.revenue.change_percent) + ' за период'
							: 'Данные не синхронизированы' }}
					</div>
				</div>

				<!-- Продано единиц -->
				<div class="stat-card success">
					<div class="stat-title">Единиц</div>
					<div class="stat-value success">
						{{ stats.sold_units?.value != null ? formatNumber(stats.sold_units.value) : '—' }}
					</div>
					<div class="stat-change">
						{{ stats.sold_units?.change_percent != null
							? formatChange(stats.sold_units.change_percent) + ' за период'
							: 'Данные не синхронизированы' }}
					</div>
				</div>

				<!-- К выплате -->
				<div class="stat-card accent">
					<div class="stat-title">К выплате</div>
					<div class="stat-value accent">
						{{ stats.to_pay?.value != null ? formatNumber(stats.to_pay.value) + ' ₽' : '—' }}
					</div>
					<div class="stat-change">
						{{ stats.to_pay?.change_percent != null
							? formatChange(stats.to_pay.change_percent) + ' за период'
							: 'Данные не синхронизированы' }}
					</div>
				</div>

				<!-- Прибыль -->
				<div class="stat-card accent">
					<div class="stat-title">Прибыль</div>
					<div class="stat-value accent">
						{{ stats.profit?.value != null ? formatNumber(stats.profit.value) + ' ₽' : '—' }}
					</div>
					<div class="stat-change">
						{{ stats.profit?.change_percent != null
							? formatChange(stats.profit.change_percent) + ' за период'
							: 'Данные не синхронизированы' }}
					</div>
				</div>

				<!-- Процент выкупа -->
				<div class="stat-card warning">
					<div class="stat-title">Процент выкупа</div>
					<div class="stat-value warning">
						{{ stats.buyout_rate?.value != null ? formatNumber(stats.buyout_rate.value) + '%' : '—' }}
					</div>
					<div class="stat-change">
						{{ stats.buyout_rate?.change_percent != null
							? formatChange(stats.buyout_rate.change_percent) + ' за период'
							: 'Данные не синхронизированы' }}
					</div>
				</div>

				<!-- Средняя цена -->
				<div class="stat-card warning">
					<div class="stat-title">Средняя цена</div>
					<div class="stat-value warning">
						{{ stats.avg_price?.value != null ? formatNumber(stats.avg_price.value) + ' ₽' : '—' }}
					</div>
					<div class="stat-change">
						{{ stats.avg_price?.change_percent != null
							? formatChange(stats.avg_price.change_percent) + ' за период'
							: 'Данные не синхронизированы' }}
					</div>
				</div>
			</div>

			<!-- Chart Container -->
			<BaseCarts :is-loading="isLoading" :chart-data="chartData" :metrics="[
				{ key: 'orders', name: 'Заказы, руб', color: '#ff9800', visible: true, type: 'rub' },
				{ key: 'buyouts', name: 'Выкупы, руб', color: '#4caf50', visible: true, type: 'rub' },
				{ key: 'avg_price', name: 'Средняя цена, руб', color: '#2196f3', visible: true, type: 'rub' },
				{ key: 'profit', name: 'Прибыль, руб', color: '#f44336', visible: true, type: 'rub' },
			]" />
			<BaseCarts :is-loading="isLoading" :chart-data="chartData" :metrics="[
				{ key: 'views', name: 'Просмотры', color: '#ffeb3b', visible: true, type: 'number' },
				{ key: 'clicks', name: 'Клики', color: '#ff9800', visible: true, type: 'number' },
				{ key: 'cart', name: 'В корзину', color: '#3f51b5', visible: true, type: 'number' },
			]" />
			<BaseCarts :is-loading="isLoading" :chart-data="chartData" :metrics="[
				{ key: 'margin', name: 'Маржинальность', color: '#9c27b0', visible: true, type: 'percent' },
				{ key: 'cr', name: 'CR', color: '#00bcd4', visible: true, type: 'percent' },
				{ key: 'ctr', name: 'CTR', color: '#8bc34a', visible: true, type: 'percent' },
				{ key: 'drr', name: 'ДРР', color: '#607d8b', visible: true, type: 'percent' }
			]" />

			<!-- Основные показатели по кабинету -->
			<BaseStats :is-loading="isLoading" :stats="baseStats" />

			<!-- ABC Analysis -->
			<AbcAnalysis :items="abcAnalysis" :isLoading="isLoading" :hasData="abcAnalysis.length > 0"
				@view="openProductModal" @edit="editProduct" @delete="confirmDelete" />
			<!-- <div class="abc-analysis">
				<div class="abc-header">
					<h2 class="abc-title">ABC Анализ</h2>
					<div class="abc-stats">
						<div class="abc-stat">
							<div class="abc-stat-label">Категория A</div>
							<div class="abc-stat-value">82%</div>
							<div class="abc-stat-subtitle">75% выручки</div>
						</div>
						<div class="abc-stat">
							<div class="abc-stat-label">Категория B</div>
							<div class="abc-stat-value">15%</div>
							<div class="abc-stat-subtitle">90% выручки</div>
						</div>
						<div class="abc-stat">
							<div class="abc-stat-label">Категория C</div>
							<div class="abc-stat-value">3%</div>
							<div class="abc-stat-subtitle">100% выручки</div>
						</div>
					</div>
				</div>
				<div class="abc-table-container">
					<table class="abc-table">
						<thead>
							<tr>
								<th>Артикул продавца</th>
								<th>Артикул WB</th>
								<th>Выручка</th>
								<th>Прибыль</th>
								<th>Доля</th>
								<th>Совокупный %</th>
								<th>Категория</th>
								<th>Действия</th>
							</tr>
						</thead>
						<tbody>
							<tr v-for="item in abcAnalysis" :key="item.id">
								<td>
									<div class="product-identifier">
										<div class="avatar">{{ item.sellerSku.substring(0, 1) }}</div>
										{{ item.sellerSku }}
									</div>
								</td>
								<td>{{ item.wbSku }}</td>
								<td class="currency">{{ item.revenue }} ₽</td>
								<td class="currency">{{ item.profit }} ₽</td>
								<td>{{ item.share }}</td>
								<td>{{ item.cumulativePercent }}</td>
								<td>
									<span :class="'abc-category abc-category-' + item.category.toLowerCase()">{{
										item.category }}</span>
								</td>
								<td>
									<div class="table-actions">
										<button class="table-action view" @click="viewProduct(item)" title="Просмотр">
											<i class="fas fa-eye"></i>
										</button>
										<button class="table-action edit" @click="editProduct(item)"
											title="Редактировать">
											<i class="fas fa-edit"></i>
										</button>
										<button class="table-action delete" @click="deleteProduct(item)"
											title="Удалить">
											<i class="fas fa-trash"></i>
										</button>
									</div>
								</td>
							</tr>
						</tbody>
					</table>
				</div>
			</div> -->

			<!-- Additional Info (может быть скрыто/показано) -->
			<div class="additional-info" v-if="showMoreInfo">
				<div class="info-section">
					<h3 class="info-title"><i class="fas fa-chart-pie"></i> Дополнительная аналитика</h3>
					<div class="info-grid">
						<div class="info-card">
							<div class="info-card-title">Средний чек</div>
							<div class="info-card-value">2 450 ₽</div>
							<div class="info-card-change success">+12%</div>
						</div>
						<div class="info-card">
							<div class="info-card-title">Конверсия</div>
							<div class="info-card-value">4.2%</div>
							<div class="info-card-change warning">-0.3%</div>
						</div>
						<div class="info-card">
							<div class="info-card-title">Возвраты</div>
							<div class="info-card-value">2.8%</div>
							<div class="info-card-change success">-0.5%</div>
						</div>
						<div class="info-card">
							<div class="info-card-title">LTV</div>
							<div class="info-card-value">15 200 ₽</div>
							<div class="info-card-change success">+8%</div>
						</div>
					</div>
				</div>
			</div>
		</div>


	</div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import DashboardService from '@/API/Dashboard/DashboardService.js'
import { notify } from '@/composables/notification';
import BaseCarts from '@/components/Diagrams/BaseCarts.vue';
import BaseStats from '@/components/BaseStats.vue';
import AbcAnalysis from '@/components/AbcAnalysis.vue';

const isLoading = ref(false);

const stats = ref({}); // основные показатели по кабинету
const chartData = ref([]); // основные данные для диаграмм
const baseStats = ref({}); // основные показатели по кабинету
const abcAnalysis = ref([]); // ABC Analysis data

// Реактивные данные
const showMoreInfo = ref(false)
const selectedChartType = ref('sales')
const selectedProductId = ref(null)
const filterStartDate = ref('')
const filterEndDate = ref('')

// Products data
const products = ref([])

// Size chart data
/* const sizeChart = ref([]) */

// Filters
/* const filters = ref([
	{ key: 'orders', label: 'Заказы, руб', checked: true, count: 125 },
	{ key: 'revenue', label: 'Выкупы, руб', checked: true, count: 98 },
	{ key: 'avgPrice', label: 'Средняя цена', checked: true, count: 45 },
	{ key: 'profit', label: 'Прибыль, руб', checked: true, count: 76 },
	{ key: 'margin', label: 'Маржинальность', checked: true, count: 32 }
]) */

// Selected products for display
const selectedProducts = ref([])

/* 
// Methods
const toggleMoreInfo = () => {
	showMoreInfo.value = !showMoreInfo.value
}

const selectProduct = (product) => {
	selectedProductId.value = product.id
	console.log('Selected product:', product)
	// Add your logic here
}

const toggleFilter = (key) => {
	const filter = filters.value.find(f => f.key === key)
	if (filter) {
		filter.checked = !filter.checked
	}
}

const applyDateFilter = () => {
	console.log('Applying date filter:', filterStartDate.value, filterEndDate.value)
	// Add your filter logic here
}

const viewProduct = (item) => {
	console.log('View product:', item)
	// Navigate to product details
}

const editProduct = (item) => {
	console.log('Edit product:', item)
	// Open edit modal
}

const deleteProduct = (item) => {
	if (confirm(`Удалить товар ${item.sellerSku}?`)) {
		console.log('Delete product:', item)
		// Delete logic
	}
}

const exportData = () => {
	console.log('Exporting data...')
	// Export logic
}

const generateReport = () => {
	console.log('Generating report...')
	// Report generation logic
}

const addProduct = () => {
	console.log('Adding new product...')
	// Add product logic
}

const refreshData = () => {
	console.log('Refreshing data...')
	// Refresh logic
}

// Computed properties
const filteredProducts = computed(() => {
	return products.value.filter(product =>
		filters.value.some(filter => filter.checked)
	)
}) */

const formatNumber = (num) => {
	return new Intl.NumberFormat('ru-RU', {
		minimumFractionDigits: num % 1 === 0 ? 0 : 2,
		maximumFractionDigits: 2
	}).format(num);
};

// Вспомогательная функция для форматирования процентов
const formatChange = (change) => {
	if (change > 0) return `+${change}%`;
	if (change < 0) return `${change}%`;
	return '0%';
};

// Lifecycle hooks
onMounted(async () => {
	// Set default dates for filter
	isLoading.value = true;

	const today = new Date()
	const lastMonth = new Date()
	lastMonth.setMonth(today.getMonth() - 1)

	filterStartDate.value = lastMonth.toISOString().split('T')[0]
	filterEndDate.value = today.toISOString().split('T')[0]

	// Fetch data
	const response = await DashboardService.get_dashboard_data();
	if (response.status === 200) {
		const result = response.data;

		if (result.status === "error") {
			notify.error(result.error.message, 3000);
			isLoading.value = false;
			return;
		}

		if (result.is_synced == false) {
			notify.warning("🔄 Данные синхронизируются с Wildberries. Обновление займёт некоторое время. Пожалуйста, подождите и перезагрузите страницу", 3000)
		}

		stats.value = result.stats;
		chartData.value = result.chartData;
		baseStats.value = result.baseStats;
		// products.value = result.products;
		// sizeChart.value = result.sizeChart;
		// abcAnalysis.value = result.abcAnalysis;

		// selectedProducts.value = result.products;
		isLoading.value = false;
	}
})
</script>

<style scoped>
/* Основная структура */
.dashboard-container {
	display: grid;
	grid-template-columns: 280px 1fr;
	gap: 20px;
	padding: 20px;
	min-height: 100vh;
}

.main-dashboard-content {
	display: flex;
	flex-direction: column;
	gap: 20px;
}

/* Dashboard Header */
.dashboard-header {
	display: flex;
	justify-content: space-between;
	align-items: center;
	margin-bottom: 20px;
	padding: 20px;
	background-color: var(--card-bg);
	border-radius: 8px;
	box-shadow: var(--shadow);
}

.dashboard-title {
	font-size: 24px;
	font-weight: 600;
	color: var(--text-color);
}

/* Stats Grid */
.stats-grid {
	display: grid;
	grid-template-columns: repeat(4, minmax(250px, 1fr));
	grid-template-rows: repeat(2, auto);
	grid-auto-flow: column;
	gap: 20px;
	margin-bottom: 20px;
}

@media (max-width: 768px) {
	.stats-grid {
		grid-template-columns: repeat(2, 1fr);
	}
}

.stat-card {
	background-color: var(--card-bg);
	border-radius: 8px;
	padding: 20px;
	box-shadow: var(--shadow);
	transition: var(--transition);
	border-left: 4px solid var(--secondary-color);
}

.stat-card.primary {
	border-left-color: var(--secondary-color);
}

.stat-card.success {
	border-left-color: var(--success-color);
}

.stat-card.warning {
	border-left-color: var(--warning-color);
}

.stat-card.accent {
	border-left-color: var(--accent-color);
}

.stat-card:hover {
	transform: translateY(-2px);
	box-shadow: 0 6px 16px rgba(0, 0, 0, 0.4);
}

.stat-title {
	font-size: 14px;
	color: #aaa;
	margin-bottom: 10px;
	text-transform: uppercase;
	letter-spacing: 0.5px;
}

.stat-value {
	font-size: 24px;
	font-weight: bold;
	margin-bottom: 5px;
}

.stat-value.primary {
	color: var(--secondary-color);
}

.stat-value.success {
	color: var(--success-color);
}

.stat-value.warning {
	color: var(--warning-color);
}

.stat-value.accent {
	color: var(--accent-color);
}

.stat-change {
	font-size: 12px;
	color: #777;
	display: flex;
	align-items: center;
	gap: 5px;
}

/* ABC Analysis */
.abc-analysis {
	background-color: var(--card-bg);
	border-radius: 8px;
	padding: 20px;
	box-shadow: var(--shadow);
	margin-bottom: 20px;
}

.abc-header {
	display: flex;
	justify-content: space-between;
	align-items: center;
	margin-bottom: 20px;
	flex-wrap: wrap;
	gap: 15px;
}

.abc-title {
	font-size: 24px;
	font-weight: 600;
	color: var(--accent-color);
	letter-spacing: 1px;
}

.abc-stats {
	display: flex;
	gap: 15px;
	flex-wrap: wrap;
}

.abc-stat {
	background-color: var(--medium-bg);
	padding: 15px 20px;
	border-radius: 6px;
	text-align: center;
	min-width: 120px;
}

.abc-stat-label {
	font-size: 14px;
	color: #aaa;
	margin-bottom: 5px;
	text-transform: uppercase;
	letter-spacing: 0.5px;
}

.abc-stat-value {
	font-size: 24px;
	font-weight: 600;
	margin-bottom: 5px;
}

.abc-stat-subtitle {
	font-size: 12px;
	color: #777;
}

.abc-table-container {
	overflow-x: auto;
	margin-top: 20px;
	border-radius: 6px;
	border: 1px solid var(--border-color);
}

.abc-table {
	width: 100%;
	border-collapse: collapse;
	min-width: 800px;
}

.abc-table th,
.abc-table td {
	padding: 12px 15px;
	text-align: left;
	border-bottom: 1px solid var(--border-color);
}

.abc-table th {
	background-color: var(--light-bg);
	font-weight: 600;
	font-size: 14px;
	text-transform: uppercase;
	letter-spacing: 0.5px;
	color: #aaa;
}

.abc-table tr:hover {
	background-color: var(--hover-bg);
}

.abc-table td.currency {
	font-family: 'Courier New', monospace;
	font-weight: 600;
}

.abc-category {
	font-weight: bold;
	padding: 4px 8px;
	border-radius: 4px;
	display: inline-block;
	font-size: 12px;
	letter-spacing: 0.5px;
}

.abc-category-a {
	background-color: var(--success-color);
	color: white;
}

.abc-category-b {
	background-color: var(--warning-color);
	color: white;
}

.abc-category-c {
	background-color: var(--info-color);
	color: white;
}

.table-actions {
	display: flex;
	gap: 5px;
}

.table-action {
	width: 30px;
	height: 30px;
	border: none;
	border-radius: 4px;
	cursor: pointer;
	display: flex;
	align-items: center;
	justify-content: center;
	transition: var(--transition);
}

.table-action.view {
	background-color: var(--secondary-color);
	color: white;
}

.table-action.edit {
	background-color: var(--info-color);
	color: white;
}

.table-action.delete {
	background-color: var(--accent-color);
	color: white;
}

.table-action:hover {
	transform: scale(1.1);
}

/* Additional Info */
.additional-info {
	background-color: var(--card-bg);
	border-radius: 8px;
	padding: 20px;
	box-shadow: var(--shadow);
	margin-top: 20px;
}

.info-section {
	margin-bottom: 20px;
}

.info-title {
	font-size: 18px;
	font-weight: 600;
	margin-bottom: 15px;
	color: var(--text-color);
	display: flex;
	align-items: center;
	gap: 10px;
}

.info-grid {
	display: grid;
	grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
	gap: 15px;
}

.info-card {
	background-color: var(--medium-bg);
	border-radius: 6px;
	padding: 15px;
	text-align: center;
}

.info-card-title {
	font-size: 14px;
	color: #aaa;
	margin-bottom: 10px;
}

.info-card-value {
	font-size: 20px;
	font-weight: 600;
	margin-bottom: 8px;
}

.info-card-change {
	font-size: 12px;
	padding: 3px 8px;
	border-radius: 12px;
	display: inline-block;
}

.info-card-change.success {
	background-color: rgba(46, 204, 113, 0.2);
	color: var(--success-color);
}

.info-card-change.warning {
	background-color: rgba(243, 156, 18, 0.2);
	color: var(--warning-color);
}

/* Sidebar */
.dashboard-sidebar {
	background-color: var(--medium-bg);
	border-radius: 8px;
	padding: 20px;
	height: fit-content;
	position: sticky;
	top: 20px;
}

.sidebar-section {
	margin-bottom: 30px;
	padding-bottom: 20px;
	border-bottom: 1px solid var(--border-color);
}

.sidebar-section:last-child {
	border-bottom: none;
	margin-bottom: 0;
	padding-bottom: 0;
}

.sidebar-title {
	font-size: 16px;
	font-weight: 600;
	margin-bottom: 15px;
	color: var(--text-color);
	display: flex;
	align-items: center;
	gap: 8px;
}

.sidebar-title i {
	color: var(--secondary-color);
}

/* Product List */
.product-list {
	list-style: none;
	max-height: 300px;
	overflow-y: auto;
}

.product-item {
	display: flex;
	align-items: center;
	padding: 12px;
	margin-bottom: 8px;
	background-color: var(--card-bg);
	border-radius: 6px;
	cursor: pointer;
	transition: var(--transition);
	border: 1px solid transparent;
}

.product-item:hover {
	background-color: var(--hover-bg);
	border-color: var(--secondary-color);
}

.product-item.active {
	border-color: var(--secondary-color);
	background-color: rgba(52, 152, 219, 0.1);
}

.product-image {
	width: 40px;
	height: 40px;
	border-radius: 4px;
	margin-right: 10px;
	background-color: var(--light-bg);
	display: flex;
	align-items: center;
	justify-content: center;
	font-size: 12px;
	font-weight: bold;
	color: var(--text-color);
}

.product-info {
	flex: 1;
	min-width: 0;
}

.product-name {
	font-size: 14px;
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
	margin-bottom: 4px;
}

.product-stats {
	display: flex;
	gap: 10px;
	font-size: 11px;
}

.stat-badge {
	padding: 2px 6px;
	border-radius: 10px;
	font-weight: 500;
}

.stat-badge.sales {
	background-color: rgba(52, 152, 219, 0.2);
	color: var(--secondary-color);
}

.stat-badge.profit {
	background-color: rgba(46, 204, 113, 0.2);
	color: var(--success-color);
}

/* Size Chart */
.size-chart-container {
	max-height: 300px;
	overflow-y: auto;
}

.size-table {
	width: 100%;
	border-collapse: collapse;
	font-size: 13px;
}

.size-table th,
.size-table td {
	padding: 8px 10px;
	text-align: left;
	border-bottom: 1px solid var(--border-color);
}

.size-table th {
	background-color: var(--light-bg);
	font-weight: 600;
	font-size: 12px;
	color: #aaa;
}

.size-table tr:last-child td {
	border-bottom: none;
}

.size-table tbody tr:hover {
	background-color: var(--hover-bg);
}

.size-badge,
.transit-badge,
.available-badge {
	padding: 2px 8px;
	border-radius: 12px;
	font-size: 11px;
	font-weight: 600;
}

.size-badge {
	background-color: var(--info-color);
	color: white;
}

.transit-badge {
	background-color: var(--warning-color);
	color: white;
}

.available-badge {
	background-color: var(--success-color);
	color: white;
}

/* Filters */
.filter-group {
	display: flex;
	flex-direction: column;
	gap: 12px;
	margin-bottom: 20px;
}

.filter-item {
	display: flex;
	align-items: center;
	gap: 10px;
	cursor: pointer;
	padding: 8px;
	border-radius: 4px;
	transition: var(--transition);
}

.filter-item:hover {
	background-color: var(--hover-bg);
}

.filter-checkbox {
	width: 18px;
	height: 18px;
	border: 2px solid var(--border-color);
	border-radius: 4px;
	display: flex;
	align-items: center;
	justify-content: center;
	cursor: pointer;
	transition: var(--transition);
}

.filter-checkbox.checked {
	background-color: var(--secondary-color);
	border-color: var(--secondary-color);
}

.filter-checkbox.checked::after {
	content: '✓';
	color: white;
	font-size: 12px;
	font-weight: bold;
}

.filter-label {
	font-size: 14px;
	flex: 1;
}

.filter-count {
	font-size: 12px;
	color: #777;
	background-color: var(--light-bg);
	padding: 2px 6px;
	border-radius: 10px;
}

/* Date Filter */
.date-filter {
	background-color: var(--card-bg);
	border-radius: 6px;
	padding: 15px;
	margin-top: 15px;
}

.filter-subtitle {
	font-size: 14px;
	font-weight: 600;
	margin-bottom: 10px;
	color: var(--text-color);
}

.date-inputs {
	display: flex;
	flex-direction: column;
	gap: 10px;
	margin-bottom: 15px;
}

.date-input-group {
	display: flex;
	flex-direction: column;
	gap: 5px;
}

.date-input-group label {
	font-size: 12px;
	color: #aaa;
}

.date-picker {
	background-color: var(--light-bg);
	border: 1px solid var(--border-color);
	color: var(--text-color);
	padding: 8px;
	border-radius: 4px;
	font-size: 14px;
}

.date-picker:focus {
	outline: none;
	border-color: var(--secondary-color);
}

.apply-filter-btn {
	width: 100%;
	padding: 8px;
	font-size: 13px;
}

/* Quick Actions */
.quick-actions {
	display: flex;
	flex-direction: column;
	gap: 10px;
}

.quick-action-btn {
	display: flex;
	align-items: center;
	gap: 10px;
	padding: 12px 15px;
	background-color: var(--card-bg);
	border: 1px solid var(--border-color);
	border-radius: 6px;
	color: var(--text-color);
	cursor: pointer;
	transition: var(--transition);
	text-align: left;
}

.quick-action-btn:hover {
	background-color: var(--hover-bg);
	border-color: var(--secondary-color);
	transform: translateX(4px);
}

.quick-action-btn i {
	color: var(--secondary-color);
	font-size: 16px;
	width: 20px;
}

.quick-action-btn span {
	font-size: 14px;
	flex: 1;
}

/* Badges */
.badge {
	padding: 4px 8px;
	border-radius: 12px;
	font-size: 12px;
	font-weight: 500;
	display: inline-block;
}

.badge-success {
	background-color: rgba(46, 204, 113, 0.2);
	color: var(--success-color);
}

.badge-warning {
	background-color: rgba(243, 156, 18, 0.2);
	color: var(--warning-color);
}

/* Avatar */
.avatar {
	width: 30px;
	height: 30px;
	border-radius: 50%;
	background-color: var(--light-bg);
	display: flex;
	align-items: center;
	justify-content: center;
	font-size: 14px;
	font-weight: bold;
	margin-right: 8px;
	color: var(--text-color);
}

.product-identifier {
	display: flex;
	align-items: center;
}

/* Responsive Design */
@media (max-width: 1200px) {
	.dashboard-container {
		grid-template-columns: 1fr;
	}

	.dashboard-sidebar {
		position: static;
	}

	.stats-grid {
		grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
	}
}

@media (max-width: 768px) {
	.dashboard-header {
		flex-direction: column;
		gap: 15px;
		text-align: center;
	}

	.chart-area {
		height: 250px;
	}

	.abc-header {
		flex-direction: column;
		align-items: flex-start;
	}

	.abc-stats {
		width: 100%;
		justify-content: space-between;
	}

	.product-images {
		grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
	}
}

@media (max-width: 480px) {
	.dashboard-container {
		padding: 10px;
	}

	.stats-grid {
		grid-template-columns: 1fr;
	}

	.product-images {
		grid-template-columns: 1fr;
	}

	.abc-stat {
		min-width: calc(50% - 8px);
	}
}
</style>