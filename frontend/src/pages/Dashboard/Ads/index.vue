<template>
	<div class="ads-dashboard-container">
		<!-- Header с датами -->
		<div class="dashboard-header">
			<div class="date-range">
				<span>Дата от</span>
				<input type="date" class="date-input" v-model="startDate">
				<span>до</span>
				<input type="date" class="date-input" v-model="endDate">
				<button class="btn btn-primary" @click="loadData">Применить</button>
			</div>
		</div>

		<!-- Состояние загрузки всей страницы -->
		<div v-if="isLoading && !hasLoadedOnce" class="page-loader">
			<div class="loading-spinner"></div>
			<p class="loading-text">Загрузка данных рекламы...</p>
		</div>

		<!-- Пустое состояние -->
		<div v-else-if="!hasData && hasLoadedOnce" class="empty-state">
			<div class="empty-icon">📊</div>
			<p class="empty-text">Нет данных для отображения</p>
			<p class="empty-hint">Данные появятся после синхронизации рекламной статистики с Wildberries</p>
		</div>

		<!-- Основной контент -->
		<div v-else>
			<!-- Динамика просмотров (график) -->
			<div class="chart-section">
				<h3 class="section-title">Динамика просмотров</h3>
				<BaseCarts :is-loading="isLoading" :chart-data="dynamicsChart" :metrics="[
					{ key: 'views', name: 'Просмотры', color: '#4caf50', visible: true, type: 'number' },
					{ key: 'clicks', name: 'Клики', color: '#ff9800', visible: true, type: 'number' },
					{ key: 'amount', name: 'Расходы, ₽', color: '#f44336', visible: true, type: 'rub' },
				]" />
			</div>

			<!-- Рекламная воронка и Конверсии -->
			<div class="stats-grid-2">
				<!-- Рекламная воронка -->
				<div class="stat-card funnel">
					<h3 class="card-title">Рекламная воронка</h3>
					<!-- Загрузка -->
					<div v-if="isLoading" class="card-loader">
						<div class="loading-spinner-small"></div>
						<p>Загрузка...</p>
					</div>
					<!-- Пустое состояние -->
					<div v-else-if="!funnelHasData" class="card-empty">
						<span>Нет данных</span>
					</div>
					<!-- Данные -->
					<div v-else class="funnel-rows">
						<div class="funnel-row">
							<span class="label">Просмотров</span>
							<span class="value">{{ formatNumber(funnel.views) }}</span>
						</div>
						<div class="funnel-row">
							<span class="label">Переходов</span>
							<span class="value">{{ formatNumber(funnel.clicks) }}</span>
						</div>
						<div class="funnel-row">
							<span class="label">Добавлений в корзину</span>
							<span class="value">{{ formatNumber(funnel.added_to_cart) }}</span>
						</div>
						<div class="funnel-row">
							<span class="label">Заказов с помощью рекламы</span>
							<span class="value">{{ formatNumber(funnel.ad_orders) }}</span>
						</div>
						<div class="funnel-row highlight">
							<span class="label">На сумму</span>
							<span class="value">{{ formatNumber(funnel.ad_orders_amount) }} ₽</span>
						</div>
						<div class="funnel-row">
							<span class="label">Общих заказов</span>
							<span class="value">{{ formatNumber(funnel.total_orders) }}</span>
						</div>
						<div class="funnel-row highlight">
							<span class="label">На сумму</span>
							<span class="value">{{ formatNumber(funnel.total_orders_amount) }} ₽</span>
						</div>
					</div>
				</div>

				<!-- Конверсии по воронке -->
				<div class="stat-card conversions">
					<h3 class="card-title">Конверсии по воронке</h3>
					<!-- Загрузка -->
					<div v-if="isLoading" class="card-loader">
						<div class="loading-spinner-small"></div>
						<p>Загрузка...</p>
					</div>
					<!-- Пустое состояние -->
					<div v-else-if="!conversionsHasData" class="card-empty">
						<span>Нет данных</span>
					</div>
					<!-- Данные -->
					<div v-else class="conversion-rows">
						<div class="conversion-row">
							<span class="label">Расходы на рекламу</span>
							<span class="value">{{ formatNumber(conversions.expenses) }} ₽</span>
						</div>
						<div class="conversion-row">
							<span class="label">CTR</span>
							<span class="value">{{ conversions.ctr }}%</span>
						</div>
						<div class="conversion-row">
							<span class="label">CR в корзину</span>
							<span class="value">{{ conversions.cr_to_cart }}%</span>
						</div>
						<div class="conversion-row">
							<span class="label">Конверсия из перехода в заказ</span>
							<span class="value">{{ conversions.conversion_click_to_order }}%</span>
						</div>
						<div class="conversion-row">
							<span class="label">CPC</span>
							<span class="value">{{ formatNumber(conversions.cpc) }} ₽</span>
						</div>
						<div class="conversion-row">
							<span class="label">CPM</span>
							<span class="value">{{ formatNumber(conversions.cpm) }} ₽</span>
						</div>
						<div class="conversion-row">
							<span class="label">ДРР</span>
							<span class="value">{{ conversions.drr }}%</span>
						</div>
					</div>
				</div>
			</div>

			<!-- Расчет стоимости привлечения -->
			<div class="stat-card acquisition">
				<h3 class="card-title">Расчет стоимости привлечения</h3>
				<!-- Загрузка -->
				<div v-if="isLoading" class="card-loader">
					<div class="loading-spinner-small"></div>
					<p>Загрузка...</p>
				</div>
				<!-- Пустое состояние -->
				<div v-else-if="!acquisitionHasData" class="card-empty">
					<span>Нет данных</span>
				</div>
				<!-- Данные -->
				<div v-else class="acquisition-grid">
					<div class="acquisition-item">
						<span class="label">Средняя стоимость заказа</span>
						<span class="value">{{ formatNumber(acquisition_cost.avg_order_value) }} ₽</span>
					</div>
					<div class="acquisition-item">
						<span class="label">Стоимость просмотра</span>
						<span class="value">{{ formatNumber(acquisition_cost.cost_per_view) }} ₽</span>
					</div>
					<div class="acquisition-item">
						<span class="label">Стоимость перехода</span>
						<span class="value">{{ formatNumber(acquisition_cost.cost_per_click) }} ₽</span>
					</div>
					<div class="acquisition-item">
						<span class="label">Стоимость добавления в корзину</span>
						<span class="value">{{ formatNumber(acquisition_cost.cost_per_cart) }} ₽</span>
					</div>
					<div class="acquisition-item highlight">
						<span class="label">CPO (стоимость одного заказа)</span>
						<span class="value">{{ formatNumber(acquisition_cost.cpo) }} ₽</span>
					</div>
					<div class="acquisition-item">
						<span class="label">Норма ДРР</span>
						<span class="value">{{ acquisition_cost.norm_drr }}%</span>
					</div>
					<div class="acquisition-item highlight">
						<span class="label">max Допустимый CPM</span>
						<span class="value">{{ formatNumber(acquisition_cost.max_cpm) }} ₽</span>
					</div>
				</div>
			</div>

			<!-- Динамика продвижения (CTR, CPM, сумма) -->
			<div class="chart-section">
				<h3 class="section-title">Динамика продвижения</h3>
				<BaseCarts :is-loading="isLoading" :chart-data="promotionDynamics" :metrics="[
					{ key: 'ctr', name: 'CTR, %', color: '#9c27b0', visible: true, type: 'percent' },
					{ key: 'cpm', name: 'CPM, ₽', color: '#00bcd4', visible: true, type: 'rub' },
					{ key: 'amount', name: 'Сумма, ₽', color: '#ff5722', visible: true, type: 'rub' },
				]" />
			</div>

			<!-- Таблица по артикулам -->
			<div class="table-section">
				<h3 class="section-title">Статистика по артикулам</h3>
				<!-- Загрузка -->
				<div v-if="isLoading" class="table-loader">
					<div class="loading-spinner-small"></div>
					<p>Загрузка таблицы...</p>
				</div>
				<!-- Пустое состояние -->
				<div v-else-if="!articlesTable.length" class="table-empty">
					<div class="empty-icon">📦</div>
					<p class="empty-text">Нет данных по артикулам</p>
				</div>
				<!-- Данные -->
				<div v-else class="table-wrapper">
					<table class="ads-table">
						<thead>
							<tr>
								<th>Фото</th>
								<th>Артикул продавца</th>
								<th>nmId</th>
								<th>Просмотры</th>
								<th>Клики</th>
								<th>В корзину</th>
								<th>Рекламные заказы</th>
								<th>Затраты</th>
								<th>Общие заказы</th>
								<th>Сумма общих заказов</th>
								<th>CTR</th>
								<th>CR</th>
								<th>Из корзины в заказ</th>
								<th>Из перехода в заказ</th>
								<th>CPC</th>
								<th>Стоимость заказа в РК</th>
								<th>ДРР от общих заказов</th>
								<th>CPM</th>
							</tr>
						</thead>
						<tbody>
							<tr v-for="item in articlesTable" :key="item.nm_id">
								<td class="photo-cell">
									<div class="product-photo-placeholder">📷</div>
								</td>
								<td>{{ item.product_name }}</td>
								<td>{{ item.nm_id }}</td>
								<td>{{ formatNumber(item.views) }}</td>
								<td>{{ formatNumber(item.clicks) }}</td>
								<td>{{ formatNumber(item.added_to_cart) }}</td>
								<td>{{ formatNumber(item.ad_orders) }}</td>
								<td>{{ formatNumber(item.expenses) }} ₽</td>
								<td>{{ formatNumber(item.total_orders) }}</td>
								<td>{{ formatNumber(item.total_orders_amount) }} ₽</td>
								<td>{{ item.ctr }}%</td>
								<td>{{ item.cr }}%</td>
								<td>{{ item.cart_to_order }}%</td>
								<td>{{ item.click_to_order }}%</td>
								<td>{{ formatNumber(item.cpc) }} ₽</td>
								<td>{{ formatNumber(item.order_cost_in_ads) }} ₽</td>
								<td>{{ item.drr_from_orders }}%</td>
								<td>{{ formatNumber(item.cpm) }} ₽</td>
							</tr>
						</tbody>
					</table>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue';
import AdsService from '@/API/Dashboard/AdsService.js';
import { notify } from '@/composables/notification';
import BaseCarts from '@/components/Diagrams/BaseCarts.vue';

const isLoading = ref(false);
const hasLoadedOnce = ref(false);

// Данные
const funnel = ref({});
const conversions = ref({});
const acquisition_cost = ref({});
const dynamicsChart = ref([]);
const promotionDynamics = ref([]);
const articlesTable = ref([]);

// Даты
const startDate = ref('');
const endDate = ref('');

// Проверка наличия данных для каждого блока
const funnelHasData = computed(() => {
	return funnel.value && Object.keys(funnel.value).length > 0;
});

const conversionsHasData = computed(() => {
	return conversions.value && Object.keys(conversions.value).length > 0;
});

const acquisitionHasData = computed(() => {
	return acquisition_cost.value && Object.keys(acquisition_cost.value).length > 0;
});

// Общая проверка наличия данных
const hasData = computed(() => {
	return funnelHasData.value || conversionsHasData.value || acquisitionHasData.value || 
		   dynamicsChart.value.length > 0 || promotionDynamics.value.length > 0 || 
		   articlesTable.value.length > 0;
});

// Форматирование чисел
const formatNumber = (num) => {
	if (num === null || num === undefined) return '—';
	return new Intl.NumberFormat('ru-RU', {
		minimumFractionDigits: num % 1 === 0 ? 0 : 2,
		maximumFractionDigits: 2
	}).format(num);
};

// Загрузка данных
const loadData = async () => {
	isLoading.value = true;
	
	try {
		const params = {};
		if (startDate.value) params.start_date = startDate.value;
		if (endDate.value) params.end_date = endDate.value;
		
		const response = await AdsService.get_ads_stats(params);
		
		if (response.status === 200) {
			const result = response.data;
			
			if (result.status === "error") {
				notify.error(result.error.message, 3000);
				isLoading.value = false;
				hasLoadedOnce.value = true;
				return;
			}
			
			funnel.value = result.data?.funnel || {};
			conversions.value = result.data?.conversions || {};
			acquisition_cost.value = result.data?.acquisition_cost || {};
			dynamicsChart.value = result.data?.dynamics_chart || [];
			promotionDynamics.value = result.data?.promotion_dynamics || [];
			articlesTable.value = result.data?.articles_table || [];
			
			hasLoadedOnce.value = true;
		}
	} catch (error) {
		console.error('Ошибка загрузки данных рекламы:', error);
		notify.error('Ошибка загрузки данных рекламы', 3000);
		hasLoadedOnce.value = true;
	} finally {
		isLoading.value = false;
	}
};

// Lifecycle
onMounted(() => {
	// Устанавливаем даты по умолчанию (последние 30 дней)
	const today = new Date();
	const lastMonth = new Date();
	lastMonth.setDate(today.getDate() - 30);
	
	startDate.value = lastMonth.toISOString().split('T')[0];
	endDate.value = today.toISOString().split('T')[0];
	
	loadData();
});
</script>

<style scoped>
.ads-dashboard-container {
	padding: 20px;
	display: flex;
	flex-direction: column;
	gap: 20px;
}

.dashboard-header {
	display: flex;
	justify-content: flex-end;
	align-items: center;
	padding: 20px;
	background-color: var(--card-bg);
	border-radius: 8px;
	box-shadow: var(--shadow);
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

.btn {
	padding: 8px 16px;
	border-radius: 6px;
	cursor: pointer;
	font-size: 14px;
	border: none;
	transition: var(--transition);
}

.btn-primary {
	background-color: var(--secondary-color);
	color: white;
}

.btn-primary:hover {
	background-color: var(--secondary-color-dark);
}

.section-title {
	font-size: 18px;
	font-weight: 600;
	margin-bottom: 15px;
	color: var(--text-color);
}

.chart-section {
	background-color: var(--card-bg);
	padding: 20px;
	border-radius: 8px;
	box-shadow: var(--shadow);
}

.stats-grid-2 {
	display: grid;
	grid-template-columns: 1fr 1fr;
	gap: 20px;
}

.stat-card {
	background-color: var(--card-bg);
	padding: 20px;
	border-radius: 8px;
	box-shadow: var(--shadow);
}

.card-title {
	font-size: 16px;
	font-weight: 600;
	margin-bottom: 15px;
	color: var(--text-color);
}

.funnel-rows, .conversion-rows {
	display: flex;
	flex-direction: column;
	gap: 10px;
}

.funnel-row, .conversion-row {
	display: flex;
	justify-content: space-between;
	align-items: center;
	padding: 8px 0;
	border-bottom: 1px solid var(--border-color);
}

.funnel-row:last-child, .conversion-row:last-child {
	border-bottom: none;
}

.funnel-row.highlight, .conversion-row.highlight {
	background-color: var(--hover-bg);
	padding: 8px 10px;
	border-radius: 6px;
	margin-top: 5px;
}

.label {
	font-size: 14px;
	color: #aaa;
}

.value {
	font-size: 14px;
	font-weight: 600;
	color: var(--text-color);
}

.acquisition-grid {
	display: grid;
	grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
	gap: 15px;
}

.acquisition-item {
	display: flex;
	flex-direction: column;
	gap: 5px;
	padding: 10px;
	background-color: var(--light-bg);
	border-radius: 6px;
}

.acquisition-item.highlight {
	background-color: var(--hover-bg);
	border: 1px solid var(--secondary-color);
}

.acquisition-item .label {
	font-size: 12px;
}

.acquisition-item .value {
	font-size: 16px;
	font-weight: 700;
}

.table-section {
	background-color: var(--card-bg);
	padding: 20px;
	border-radius: 8px;
	box-shadow: var(--shadow);
}

.table-wrapper {
	overflow-x: auto;
}

.ads-table {
	width: 100%;
	border-collapse: collapse;
	font-size: 13px;
}

.ads-table th, .ads-table td {
	padding: 10px 8px;
	text-align: left;
	border-bottom: 1px solid var(--border-color);
}

.ads-table th {
	background-color: var(--light-bg);
	font-weight: 600;
	color: var(--text-color);
	white-space: nowrap;
}

.ads-table tr:hover {
	background-color: var(--hover-bg);
}

.photo-cell {
	text-align: center;
}

.product-photo-placeholder {
	width: 40px;
	height: 40px;
	background-color: var(--light-bg);
	border-radius: 6px;
	display: flex;
	align-items: center;
	justify-content: center;
	font-size: 20px;
	margin: 0 auto;
}

.no-data {
	text-align: center;
	padding: 20px;
	color: #aaa;
}
</style>
