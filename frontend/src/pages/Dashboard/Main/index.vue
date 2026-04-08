<template>
	<div class="dashboard-container">
		<!-- Сайдбар -->
		<aside class="dashboard-sidebar">
			<WarehouseChart :data="warehouseData" :is-loading="isLoading" />
			<DonutChart :data="categoryData" :is-loading="isLoading" />
		</aside>
		<!-- Основное содержимое дашборда -->
		<div class="main-dashboard-content">
			<!-- Dashboard Header -->
			<div class="dashboard-header">
				<div class="search-container">
					<input type="text" class="search-input" placeholder="Выберите артикул..." v-model="searchQuery">
				</div>
				<div class="date-range">
					<span>Дата от</span>
					<input type="text" class="date-input" placeholder="1 октября" v-model="startDate">
					<span>до</span>
					<input type="text" class="date-input" placeholder="19 октября" v-model="endDate">
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

		<aside class="dashboard-sidebar">
			<div class="stat-card">
				<div class="stat-title">Маржинальность</div>
				<div class="stat-value primary">
					{{ stats.ordered_amount?.value != null ? formatNumber(stats.ordered_amount.value) + ' %' : '—'
					}}
				</div>
			</div>
			<div class="stat-card">
				<div class="stat-title">Рентабельность</div>
				<div class="stat-value primary">
					{{ stats.ordered_amount?.value != null ? formatNumber(stats.ordered_amount.value) + ' %' : '—'
					}}
				</div>
			</div>
			<div class="stat-card">
				<div class="stat-title">ДДР</div>
				<div class="stat-value primary">
					{{ stats.ordered_amount?.value != null ? formatNumber(stats.ordered_amount.value) + ' %' : '—'
					}}
				</div>
			</div>
		</aside>
		<aside class="dashboard-sidebar">
			<div class="stat-card">
				<div class="stat-title">Маржинальность</div>
				<div class="stat-value primary">
					{{ stats.ordered_amount?.value != null ? formatNumber(stats.ordered_amount.value) + ' %' : '—'
					}}
				</div>
			</div>
			<div class="stat-card">
				<div class="stat-title">Рентабельность</div>
				<div class="stat-value primary">
					{{ stats.ordered_amount?.value != null ? formatNumber(stats.ordered_amount.value) + ' %' : '—'
					}}
				</div>
			</div>
			<div class="stat-card">
				<div class="stat-title">ДДР</div>
				<div class="stat-value primary">
					{{ stats.ordered_amount?.value != null ? formatNumber(stats.ordered_amount.value) + ' %' : '—'
					}}
				</div>
			</div>
		</aside>
	</div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import DashboardService from '@/API/Dashboard/DashboardService.js'
import { notify } from '@/composables/notification';
import BaseCarts from '@/components/Diagrams/BaseCarts.vue';
import WarehouseChart from '@/components/Diagrams/WarehouseChart.vue';
import BaseStats from '@/components/Widgets/BaseStats.vue';
import AbcAnalysis from '@/components/Widgets/AbcAnalysis.vue';
import DonutChart from '@/components/Diagrams/DonutChart.vue';

const isLoading = ref(false);

const stats = ref({}); // основные показатели по кабинету
const chartData = ref([]); // основные данные для диаграмм
const baseStats = ref({}); // основные показатели по кабинету
const abcAnalysis = ref([]); // ABC Analysis data
const warehouseData = ref([]) // Данные склада
const categoryData = ref([]); // Данные по категориям

// Навигация и поиск
const searchQuery = ref('')
const startDate = ref('1 октября')
const endDate = ref('19 октября')

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
		categoryData.value = result.categoryData;
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
	grid-template-columns: 280px 1fr 280px;
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

/* Search Bar */
.search-container {
	display: flex;
	align-items: center;
	background-color: var(--light-bg);
	border-radius: 6px;
	padding: 8px 12px;
	width: 250px;
}

.search-input {
	flex: 1;
	background: transparent;
	border: none;
	color: var(--text-color);
	padding: 4px 8px;
	font-size: 14px;
}

.search-input:focus {
	outline: none;
}

.date-range {
	display: flex;
	align-items: center;
	gap: 10px;
	font-size: 14px;
}

.date-input {
	background-color: var(--light-bg);
	border: none;
	color: var(--text-color);
	padding: 6px 10px;
	border-radius: 4px;
	font-size: 14px;
}

.date-input:focus {
	outline: none;
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

@media screen and (max-width: 1700px) {
	.stats-grid {
		grid-template-columns: repeat(3, minmax(250px, 1fr));
		grid-template-rows: repeat(3, auto);
	}
}

@media screen and (max-width: 1440px) {
	.stats-grid {
		grid-template-columns: repeat(2, minmax(250px, 1fr));
		grid-template-rows: repeat(4, auto);
		grid-auto-flow: row;

	}
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
	display: flex;
	flex-direction: column;
	gap: 15px;
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