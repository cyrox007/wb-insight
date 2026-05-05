<template>
	<div class="unit-economy-table">
		<h2 class="table-title">📋 Детализация по артикулам</h2>
		
		<!-- Состояние загрузки -->
		<div v-if="isLoading" class="table-loading">
			<div class="loading-spinner"></div>
			<p class="loading-text">Загрузка данных...</p>
		</div>

		<!-- Пустое состояние -->
		<div v-else-if="!hasData" class="table-empty">
			<div class="empty-icon">📊</div>
			<p class="empty-text">Нет данных для отображения</p>
		</div>

		<!-- Таблица -->
		<div v-else class="table-wrapper">
			<table class="data-table">
				<thead>
					<tr>
						<th class="col-article">Артикул WB</th>
						<th class="col-money">Сумма продаж без СПП</th>
						<th class="col-money">Сумма продаж с СПП</th>
						<th class="col-money">Сумма возвратов</th>
						<th class="col-number">Количество продаж</th>
						<th class="col-number">Количество доставок</th>
						<th class="col-number">Возвратов</th>
						<th class="col-percent">Процент выкупа</th>
						<th class="col-money">Эквайринг</th>
						<th class="col-percent">Размер кВВ %</th>
						<th class="col-money">К перечислению</th>
						<th class="col-money">Логистика</th>
						<th class="col-money">Хранение</th>
						<th class="col-money">Штраф</th>
						<th class="col-money">Прочие удержания</th>
						<th class="col-money">Налог</th>
						<th class="col-money">Расходы на РК</th>
						<th class="col-percent">ДРР</th>
						<th class="col-money">Платная приемка</th>
						<th class="col-money">Итого к оплате</th>
						<th class="col-money">Себестоимость</th>
						<th class="col-money">Все расходы</th>
						<th class="col-money profit">Прибыль</th>
						<th class="col-money">Прибыль на 1 ед.</th>
						<th class="col-percent">Маржинальность</th>
						<th class="col-percent">Рентабельность</th>
						<th class="col-money">Средняя стоимость продажи</th>
					</tr>
				</thead>
				<tbody>
					<tr v-for="(row, index) in data" :key="index" class="data-row">
						<td class="col-article">{{ row.wb_article || '—' }}</td>
						<td class="col-money">{{ formatCurrency(row.sales_without_spp) }}</td>
						<td class="col-money">{{ formatCurrency(row.sales_with_spp) }}</td>
						<td class="col-money">{{ formatCurrency(row.returns_amount) }}</td>
						<td class="col-number">{{ formatNumber(row.sales_qty) }}</td>
						<td class="col-number">{{ formatNumber(row.deliveries_qty) }}</td>
						<td class="col-number">{{ formatNumber(row.returns_qty) }}</td>
						<td class="col-percent" :class="getBuyoutClass(row.buyout_percent)">{{ formatPercent(row.buyout_percent) }}</td>
						<td class="col-money">{{ formatCurrency(row.acquiring) }}</td>
						<td class="col-percent">{{ formatPercent(row.wb_commission_percent) }}</td>
						<td class="col-money highlight">{{ formatCurrency(row.to_pay_seller) }}</td>
						<td class="col-money">{{ formatCurrency(row.logistics_total) }}</td>
						<td class="col-money">{{ formatCurrency(row.storage) }}</td>
						<td class="col-money">{{ formatCurrency(row.fines) }}</td>
						<td class="col-money">{{ formatCurrency(row.other_deductions) }}</td>
						<td class="col-money">{{ formatCurrency(row.tax) }}</td>
						<td class="col-money">{{ formatCurrency(row.ad_expenses) }}</td>
						<td class="col-percent">{{ formatPercent(row.drr) }}</td>
						<td class="col-money">{{ formatCurrency(row.paid_acceptance) }}</td>
						<td class="col-money highlight">{{ formatCurrency(row.total_to_pay) }}</td>
						<td class="col-money">{{ formatCurrency(row.cost_price_total) }}</td>
						<td class="col-money">{{ formatCurrency(row.total_expenses) }}</td>
						<td class="col-money profit" :class="getProfitClass(row.profit)">{{ formatCurrency(row.profit) }}</td>
						<td class="col-money" :class="getProfitClass(row.profit_per_unit)">{{ formatCurrency(row.profit_per_unit) }}</td>
						<td class="col-percent" :class="getMarginClass(row.margin)">{{ formatPercent(row.margin) }}</td>
						<td class="col-percent" :class="getProfitabilityClass(row.profitability)">{{ formatPercent(row.profitability) }}</td>
						<td class="col-money">{{ formatCurrency(row.avg_sale_price) }}</td>
					</tr>
				</tbody>
			</table>
		</div>
	</div>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
	data: {
		type: Array,
		default: () => []
	},
	isLoading: {
		type: Boolean,
		default: false
	}
});

const hasData = computed(() => props.data && props.data.length > 0);

const formatCurrency = (value) => {
	if (value === null || value === undefined || isNaN(value)) return '—';
	return new Intl.NumberFormat('ru-RU', {
		minimumFractionDigits: 2,
		maximumFractionDigits: 2
	}).format(value) + ' ₽';
};

const formatNumber = (value) => {
	if (value === null || value === undefined || isNaN(value)) return '—';
	return new Intl.NumberFormat('ru-RU').format(Math.round(value));
};

const formatPercent = (value) => {
	if (value === null || value === undefined || isNaN(value)) return '—';
	return new Intl.NumberFormat('ru-RU', {
		minimumFractionDigits: 2,
		maximumFractionDigits: 2
	}).format(value) + '%';
};

// Подсветка процента выкупа
const getBuyoutClass = (value) => {
	if (value === null || value === undefined) return '';
	if (value >= 50) return 'value-excellent';    // Отлично (зеленый)
	if (value >= 40) return 'value-good';         // Хорошо (светло-зеленый)
	if (value >= 30) return 'value-warning';      // Нормально (желтый)
	return 'value-bad';                           // Плохо (красный)
};

// Подсветка прибыли
const getProfitClass = (value) => {
	if (value === null || value === undefined) return '';
	if (value > 0) return 'value-positive';       // Положительная (зеленый)
	if (value > -1000) return 'value-warning';    // Небольшой убыток (желтый)
	return 'value-negative';                      // Убыток (красный)
};

// Подсветка маржинальности
const getMarginClass = (value) => {
	if (value === null || value === undefined) return '';
	if (value >= 60) return 'value-excellent';    // Отлично
	if (value >= 40) return 'value-good';         // Хорошо
	if (value >= 20) return 'value-warning';      // Нормально
	return 'value-bad';                           // Плохо
};

// Подсветка рентабельности
const getProfitabilityClass = (value) => {
	if (value === null || value === undefined) return '';
	if (value >= 100) return 'value-excellent';   // Отлично
	if (value >= 50) return 'value-good';         // Хорошо
	if (value >= 20) return 'value-warning';      // Нормально
	return 'value-bad';                           // Плохо
};
</script>

<style scoped>
.unit-economy-table {
	width: 100%;
}

.table-title {
	font-size: 20px;
	font-weight: 600;
	color: var(--text-color);
	margin-bottom: 20px;
	padding-bottom: 12px;
	border-bottom: 2px solid rgba(255, 107, 107, 0.3);
}

/* Загрузка */
.table-loading {
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	padding: 60px 20px;
	color: #888;
}

.loading-spinner {
	width: 32px;
	height: 32px;
	border: 3px solid rgba(255, 255, 255, 0.3);
	border-radius: 50%;
	border-top-color: #ff6b6b;
	animation: spin 1s linear infinite;
	margin-bottom: 16px;
}

@keyframes spin {
	to {
		transform: rotate(360deg);
	}
}

.loading-text {
	font-size: 14px;
	color: #888;
}

/* Пустое состояние */
.table-empty {
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	padding: 60px 20px;
	color: #888;
	text-align: center;
}

.empty-icon {
	font-size: 48px;
	margin-bottom: 16px;
	opacity: 0.6;
}

.empty-text {
	font-size: 16px;
	font-weight: 500;
	margin: 0;
	color: var(--text-color);
}

/* Таблица */
.table-wrapper {
	overflow-x: auto;
	border-radius: 8px;
}

.data-table {
	width: 100%;
	border-collapse: collapse;
	font-size: 13px;
}

.data-table th {
	background: rgba(255, 107, 107, 0.1);
	color: var(--text-color);
	font-weight: 600;
	padding: 12px 8px;
	text-align: right;
	white-space: nowrap;
	border-bottom: 2px solid rgba(255, 107, 107, 0.3);
}

.data-table th.col-article {
	text-align: left;
	min-width: 120px;
}

.data-table td {
	padding: 10px 8px;
	text-align: right;
	border-bottom: 1px solid rgba(255, 255, 255, 0.05);
	white-space: nowrap;
}

.data-table tbody tr:hover {
	background: rgba(255, 255, 255, 0.03);
}

/* Выделение колонок */
.col-article {
	text-align: left !important;
	font-weight: 600;
	color: var(--text-color);
}

.col-money {
	font-family: 'Courier New', monospace;
}

.col-percent {
	font-family: 'Courier New', monospace;
}

.col-number {
	font-family: 'Courier New', monospace;
}

/* Подсветка важных значений */
.highlight {
	font-weight: 700;
	color: #ff6b6b;
}

.profit {
	font-weight: 700;
}

/* Цветовая индикация значений */
.value-excellent {
	color: #4caf50;
	font-weight: 600;
}

.value-good {
	color: #8bc34a;
	font-weight: 600;
}

.value-warning {
	color: #ff9800;
	font-weight: 600;
}

.value-bad {
	color: #f44336;
	font-weight: 600;
}

.value-positive {
	color: #4caf50;
	font-weight: 600;
}

.value-negative {
	color: #f44336;
	font-weight: 600;
}

/* Адаптивность */
@media screen and (max-width: 1200px) {
	.data-table {
		font-size: 12px;
	}
	
	.data-table th,
	.data-table td {
		padding: 8px 4px;
	}
}
</style>
