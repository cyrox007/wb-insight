<template>
	<div class="dashboard-container">
		<!-- Сайдбар -->
		<aside class="dashboard-sidebar">
			<!-- Key Indicators -->
			<div class="sidebar-section">
				<h3 class="sidebar-title"><i class="fas fa-chart-line"></i> Ключевые показатели</h3>
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
				<h3 class="sidebar-title"><i class="fas fa-ruler"></i> Размерная сетка</h3>
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
				<h3 class="sidebar-title"><i class="fas fa-filter"></i> Фильтры</h3>
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
				<h3 class="sidebar-title"><i class="fas fa-bolt"></i> Быстрые действия</h3>
				<div class="quick-actions">
					<button class="quick-action-btn" @click="exportData">
						<i class="fas fa-file-export"></i>
						<span>Экспорт данных</span>
					</button>
					<button class="quick-action-btn" @click="generateReport">
						<i class="fas fa-chart-bar"></i>
						<span>Создать отчет</span>
					</button>
					<button class="quick-action-btn" @click="addProduct">
						<i class="fas fa-plus"></i>
						<span>Добавить товар</span>
					</button>
					<button class="quick-action-btn" @click="refreshData">
						<i class="fas fa-sync-alt"></i>
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
						<i class="fas fa-info-circle"></i> Больше информации
					</button>
				</div>
			</div>

			<!-- Stats Grid -->
			<div class="stats-grid">
				<div class="stat-card">
					<div class="stat-title">Комиссия</div>
					<div class="stat-value primary">29,2%</div>
					<div class="stat-change">+2,1% за период</div>
				</div>
				<div class="stat-card">
					<div class="stat-title">Заказано на сумму</div>
					<div class="stat-value success">18 118 832,0 ₽</div>
					<div class="stat-change">+15,3% за период</div>
				</div>
				<div class="stat-card">
					<div class="stat-title">Выручка</div>
					<div class="stat-value warning">3 747 120,0 ₽</div>
					<div class="stat-change">+8,7% за период</div>
				</div>
				<div class="stat-card">
					<div class="stat-title">К выплате</div>
					<div class="stat-value accent">1 994 325,4 ₽</div>
					<div class="stat-change">+5,2% за период</div>
				</div>
				<div class="stat-card">
					<div class="stat-title">Прибыль</div>
					<div class="stat-value success">1 768 051,17 ₽</div>
					<div class="stat-change">+12,4% за период</div>
				</div>
				<div class="stat-card">
					<div class="stat-title">Маржинальность</div>
					<div class="stat-value warning">16,5%</div>
					<div class="stat-change">+1,8% за период</div>
				</div>
			</div>

			<!-- Chart Container -->
			<div class="chart-container">
				<div class="chart-header">
					<h2 class="chart-title">Сводные данные по дням</h2>
					<div class="chart-controls">
						<select class="chart-dropdown" v-model="selectedChartType">
							<option value="sales">Продажи</option>
							<option value="revenue">Выручка</option>
							<option value="profit">Прибыль</option>
							<option value="margin">Маржинальность</option>
						</select>
					</div>
				</div>
				<div class="chart-area">
					<div class="chart-bar-container">
						<div v-for="(data, index) in chartData" :key="index" class="chart-bar"
							:style="{ height: data.value + '%' }"
							:title="`${data.label}: ${getChartValue(data.value)}`">
							<div class="chart-bar-label">{{ data.label }}</div>
						</div>
					</div>
				</div>
			</div>

			<!-- Product Images -->
			<div class="product-images">
				<div v-for="product in selectedProducts" :key="product.id" class="product-image-card">
					<div class="product-image-wrapper">
						<div class="product-image-img">
							<img :src="product.image" :alt="product.name"
								style="width: 100%; height: 100%; object-fit: cover;">
						</div>
					</div>
					<div class="product-image-info">
						<div class="product-image-title">{{ product.name }}</div>
						<div class="product-image-price">{{ product.price }} ₽</div>
						<div class="product-image-stats">
							<span class="badge badge-success">{{ product.sales || 0 }} продаж</span>
							<span class="badge badge-warning">{{ product.rating || '4.5' }} ★</span>
						</div>
					</div>
				</div>
			</div>

			<!-- ABC Analysis -->
			<div class="abc-analysis">
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
			</div>

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
import { ref, computed, onMounted } from 'vue'

// Реактивные данные
const showMoreInfo = ref(false)
const selectedChartType = ref('sales')
const selectedProductId = ref(null)
const filterStartDate = ref('')
const filterEndDate = ref('')

// Products data
const products = ref([
	{ id: 1, name: 'Электросталь', sales: 2722, profit: 1500 },
	{ id: 2, name: 'Коледино', sales: 1323, profit: 800 },
	{ id: 3, name: 'Казань', sales: 638, profit: 400 },
	{ id: 4, name: 'Рязань', sales: 746, profit: 500 },
	{ id: 5, name: 'Невинномысск', sales: 550, profit: 300 },
	{ id: 6, name: 'Екатеринбург', sales: 473, profit: 250 },
	{ id: 7, name: 'Самара', sales: 460, profit: 200 },
	{ id: 8, name: 'Санкт-Петербург', sales: 388, profit: 180 },
	{ id: 9, name: 'Новосибирск', sales: 259, profit: 150 },
	{ id: 10, name: 'Котовск', sales: 157, profit: 100 },
	{ id: 11, name: 'Владимир', sales: 124, profit: 80 },
	{ id: 12, name: 'Волгоград', sales: 122, profit: 70 },
	{ id: 13, name: 'Воронеж', sales: 105, profit: 60 },
	{ id: 14, name: 'Саратов', sales: 74, profit: 40 },
	{ id: 15, name: 'Екатеринбург', sales: 52, profit: 30 },
	{ id: 16, name: 'Астана', sales: 15, profit: 10 },
	{ id: 17, name: 'Белая дача', sales: 15, profit: 10 },
	{ id: 18, name: 'Актобе', sales: 13, profit: 8 },
	{ id: 19, name: 'Атакент', sales: 8, profit: 5 },
	{ id: 20, name: 'Калининград', sales: 7, profit: 4 },
	{ id: 21, name: 'СЦ Ереван', sales: 5, profit: 3 },
	{ id: 22, name: 'Чашниково', sales: 3, profit: 2 },
	{ id: 23, name: 'Обухово', sales: 1, profit: 1 },
	{ id: 24, name: 'СЦ Барнаул', sales: 1, profit: 1 }
])

// Size chart data
const sizeChart = ref([
	{ size: '40', quantity: 2447, inTransit: 87 },
	{ size: '42', quantity: 1939, inTransit: 261 },
	{ size: '44', quantity: 1534, inTransit: 301 },
	{ size: '46', quantity: 1380, inTransit: 203 },
	{ size: '48', quantity: 1381, inTransit: 238 },
	{ size: '50', quantity: 973, inTransit: 213 },
	{ size: '52', quantity: 752, inTransit: 207 },
	{ size: '54', quantity: 587, inTransit: 111 },
	{ size: '56', quantity: 428, inTransit: 83 },
	{ size: '58', quantity: 7, inTransit: 0 }
])

// Filters
const filters = ref([
	{ key: 'orders', label: 'Заказы, руб', checked: true, count: 125 },
	{ key: 'revenue', label: 'Выкупы, руб', checked: true, count: 98 },
	{ key: 'avgPrice', label: 'Средняя цена', checked: true, count: 45 },
	{ key: 'profit', label: 'Прибыль, руб', checked: true, count: 76 },
	{ key: 'margin', label: 'Маржинальность', checked: true, count: 32 }
])

// Selected products for display
const selectedProducts = ref([
	{
		id: 1,
		name: 'Темно-синее пальто',
		price: '12 999',
		image: 'https://placehold.co/200x300/2c3e50/ffffff?text=Пальто',
		sales: 150,
		rating: 4.8
	},
	{
		id: 2,
		name: 'Черная зимняя куртка',
		price: '15 999',
		image: 'https://placehold.co/200x300/000000/ffffff?text=Куртка',
		sales: 120,
		rating: 4.5
	},
	{
		id: 3,
		name: 'Бежевое пуховое пальто',
		price: '18 999',
		image: 'https://placehold.co/200x300/d2b48c/ffffff?text=Пуховик',
		sales: 95,
		rating: 4.9
	},
	{
		id: 4,
		name: 'Зеленое зимнее пальто',
		price: '14 999',
		image: 'https://placehold.co/200x300/556b2f/ffffff?text=Пальто',
		sales: 85,
		rating: 4.3
	}
])

// ABC Analysis data
const abcAnalysis = ref([
	{ id: 1, sellerSku: 'АтласРубашкаНова', wbSku: '182440753', revenue: '624 572,9', profit: '348 148,4', share: '22,8%', cumulativePercent: '22,8%', category: 'A' },
	{ id: 2, sellerSku: 'РубашкаШелк-01-зп', wbSku: '152048084', revenue: '324 707,9', profit: '172 073,6', share: '11,3%', cumulativePercent: '34,1%', category: 'A' },
	{ id: 3, sellerSku: 'АтласРубашкаНова', wbSku: '219169078', revenue: '208 559,2', profit: '143 802,8', share: '9,4%', cumulativePercent: '43,6%', category: 'A' },
	{ id: 4, sellerSku: 'АтласРубашкаНова', wbSku: '190442797', revenue: '189 835,0', profit: '111 008,8', share: '7,3%', cumulativePercent: '50,9%', category: 'A' },
	{ id: 5, sellerSku: 'ВолнистаяБлузка-0', wbSku: '388639444', revenue: '177 276,6', profit: '99 807,4', share: '6,5%', cumulativePercent: '57,4%', category: 'A' },
	{ id: 6, sellerSku: 'ПлатьеОдноПлехо-1', wbSku: '391354791', revenue: '214 603,6', profit: '91 153,8', share: '6,0%', cumulativePercent: '63,4%', category: 'A' },
	{ id: 7, sellerSku: 'АтласРубашкаНова', wbSku: '334837164', revenue: '120 756,0', profit: '84 180,7', share: '5,5%', cumulativePercent: '68,9%', category: 'A' },
	{ id: 8, sellerSku: 'РубашкаШелк-01-ч', wbSku: '144826387', revenue: '138 890,4', profit: '80 063,8', share: '5,3%', cumulativePercent: '74,2%', category: 'A' },
	{ id: 9, sellerSku: 'БлузкаПланка-01-б', wbSku: '104098349', revenue: '100 457,5', profit: '66 591,8', share: '4,4%', cumulativePercent: '78,5%', category: 'B' },
	{ id: 10, sellerSku: 'ПальтоХалатДрап-С', wbSku: '170206280', revenue: '114 379,2', profit: '58 267,9', share: '3,8%', cumulativePercent: '82,3%', category: 'B' }
])

// Chart data
const chartData = ref([
	{ label: '01.10', value: 80 },
	{ label: '02.10', value: 90 },
	{ label: '03.10', value: 70 },
	{ label: '04.10', value: 75 },
	{ label: '05.10', value: 65 },
	{ label: '06.10', value: 70 },
	{ label: '07.10', value: 75 },
	{ label: '08.10', value: 85 },
	{ label: '09.10', value: 80 },
	{ label: '10.10', value: 60 },
	{ label: '11.10', value: 70 },
	{ label: '12.10', value: 90 },
	{ label: '13.10', value: 65 },
	{ label: '14.10', value: 70 },
	{ label: '15.10', value: 95 },
	{ label: '16.10', value: 80 },
	{ label: '17.10', value: 60 },
	{ label: '18.10', value: 75 },
	{ label: '19.10', value: 80 }
])

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

const getChartValue = (percentage) => {
	// Convert percentage to actual value based on chart type
	const maxValues = {
		sales: 1000,
		revenue: 500000,
		profit: 250000,
		margin: 100
	}
	const maxValue = maxValues[selectedChartType.value] || 1000
	return Math.round((percentage / 100) * maxValue).toLocaleString('ru-RU')
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
})

// Lifecycle hooks
onMounted(() => {
	// Set default dates for filter
	const today = new Date()
	const lastMonth = new Date()
	lastMonth.setMonth(today.getMonth() - 1)

	filterStartDate.value = lastMonth.toISOString().split('T')[0]
	filterEndDate.value = today.toISOString().split('T')[0]

	console.log('Dashboard mounted')
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
	grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
	gap: 20px;
	margin-bottom: 20px;
}

.stat-card {
	background-color: var(--card-bg);
	border-radius: 8px;
	padding: 20px;
	box-shadow: var(--shadow);
	transition: var(--transition);
	border-left: 4px solid var(--secondary-color);
}

.stat-card:nth-child(2) {
	border-left-color: var(--success-color);
}

.stat-card:nth-child(3) {
	border-left-color: var(--warning-color);
}

.stat-card:nth-child(4) {
	border-left-color: var(--accent-color);
}

.stat-card:nth-child(5) {
	border-left-color: var(--success-color);
}

.stat-card:nth-child(6) {
	border-left-color: var(--warning-color);
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

/* Chart Container */
.chart-container {
	background-color: var(--card-bg);
	border-radius: 8px;
	padding: 20px;
	box-shadow: var(--shadow);
	margin-bottom: 20px;
}

.chart-header {
	display: flex;
	justify-content: space-between;
	align-items: center;
	margin-bottom: 15px;
}

.chart-title {
	font-size: 18px;
	font-weight: 600;
}

.chart-controls {
	display: flex;
	gap: 10px;
}

.chart-dropdown {
	background-color: var(--light-bg);
	border: 1px solid var(--border-color);
	color: var(--text-color);
	padding: 8px 12px;
	border-radius: 6px;
	font-size: 14px;
	cursor: pointer;
}

.chart-dropdown:focus {
	outline: none;
	border-color: var(--secondary-color);
}

.chart-area {
	height: 300px;
	background-color: var(--medium-bg);
	border-radius: 6px;
	position: relative;
	padding: 20px;
}

.chart-bar-container {
	width: 100%;
	height: 100%;
	display: flex;
	align-items: flex-end;
	justify-content: space-around;
	gap: 8px;
}

.chart-bar {
	flex: 1;
	max-width: 40px;
	background: linear-gradient(to top, var(--secondary-color), var(--accent-color));
	border-radius: 4px 4px 0 0;
	transition: var(--transition);
	position: relative;
	cursor: pointer;
}

.chart-bar:hover {
	transform: scaleY(1.05);
	filter: brightness(1.2);
}

.chart-bar-label {
	position: absolute;
	bottom: -25px;
	left: 50%;
	transform: translateX(-50%);
	font-size: 12px;
	color: #aaa;
	white-space: nowrap;
}

/* Product Images */
.product-images {
	display: grid;
	grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
	gap: 20px;
	margin-bottom: 20px;
}

.product-image-card {
	background-color: var(--card-bg);
	border-radius: 8px;
	overflow: hidden;
	box-shadow: var(--shadow);
	transition: var(--transition);
}

.product-image-card:hover {
	transform: translateY(-4px);
	box-shadow: 0 8px 20px rgba(0, 0, 0, 0.5);
}

.product-image-wrapper {
	height: 250px;
	background-color: var(--medium-bg);
	display: flex;
	align-items: center;
	justify-content: center;
	overflow: hidden;
}

.product-image-img img {
	width: 100%;
	height: 100%;
	object-fit: cover;
}

.product-image-info {
	padding: 15px;
}

.product-image-title {
	font-size: 16px;
	font-weight: 600;
	margin-bottom: 8px;
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}

.product-image-price {
	font-size: 18px;
	color: var(--secondary-color);
	font-weight: 600;
	margin-bottom: 8px;
}

.product-image-stats {
	display: flex;
	gap: 8px;
	flex-wrap: wrap;
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