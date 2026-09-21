<template>
	<div class="stats-block">
		<h2 class="stats-header">Общие показатели по кабинету</h2>

		<!-- Состояние загрузки -->
		<div v-if="isLoading" class="stats-loading">
			<div class="loading-spinner"></div>
			<p class="loading-text">Загрузка показателей...</p>
		</div>

		<!-- Пустое состояние -->
		<div v-else-if="!hasData" class="stats-empty">
			<div class="empty-icon">📊</div>
			<p class="empty-text">Нет данных для отображения</p>
			<p class="empty-hint">Данные появятся после синхронизации с Wildberries</p>
		</div>

		<!-- Основные данные -->
		<div v-else class="stats-grid">
			<!-- Первая группа -->
			<div class="stats-group">
				<div class="stats-row">
					<div class="stats-label">Просмотры Рекламы</div>
					<div class="stats-value">
						<span>{{ formatValue(stats.adViews) }}</span>
						<span class="stats-icon">📈</span>
					</div>
				</div>

				<div class="stats-row">
					<div class="stats-label">Клики</div>
					<div class="stats-value">
						<span>{{ formatValue(stats.clicks) }}</span>
						<span class="stats-percentage">{{ formatPercentage(stats.clicksPercentage) }}%</span>
					</div>
				</div>

				<div class="stats-row">
					<div class="stats-label">Добавлено в корзину</div>
					<div class="stats-value">
						<span>{{ formatValue(stats.addToCart) }}</span>
						<span class="stats-percentage">{{ formatPercentage(stats.addToCartPercentage) }}%</span>
					</div>
				</div>
			</div>

			<!-- Вторая группа -->
			<div class="stats-group">
				<div class="stats-row">
					<div class="stats-label">Заказано всего</div>
					<div class="stats-value">
						<span>{{ formatValue(stats.orderedTotalCount) }}</span>
						<span class="stats-secondary">{{ formatValue(stats.orderedTotalAmount) }} ₽</span>
					</div>
				</div>

				<div class="stats-row">
					<div class="stats-label">Выкуплено всего</div>
					<div class="stats-value">
						<span>{{ formatValue(stats.boughtTotalCount) }}</span>
						<span class="stats-secondary">{{ formatValue(stats.boughtTotalAmount) }} ₽</span>
					</div>
				</div>

				<div class="stats-row">
					<div class="stats-label">Процент выкупа</div>
					<div class="stats-value">
						<span class="stats-value--red">{{ formatPercentage(stats.buyoutPercent) }}%</span>
					</div>
				</div>
			</div>

			<!-- Третья группа -->
			<div class="stats-group">
				<div class="stats-row">
					<div class="stats-label">Средняя стоимость заказа</div>
					<div class="stats-value">
						<span>{{ formatValue(stats.avgOrderValue) }} ₽</span>
					</div>
				</div>

				<div class="stats-row">
					<div class="stats-label">Маржинальность</div>
					<div class="stats-value">
						<span class="stats-value--red">{{ formatPercentage(stats.marginality) }}%</span>
					</div>
				</div>

				<div class="stats-row">
					<div class="stats-label">Доля расходов от продаж</div>
					<div class="stats-value">
						<span>{{ formatPercentage(stats.expenseRatio) }}%</span>
					</div>
				</div>

				<div class="stats-row">
					<div class="stats-label">Прибыль</div>
					<div class="stats-value">
						<span class="stats-value--red">{{ formatValue(stats.profit) }} ₽</span>
					</div>
				</div>

				<div class="stats-row">
					<div class="stats-label">Выручка</div>
					<div class="stats-value">
						<span>{{ formatValue(stats.revenue) }} ₽</span>
					</div>
				</div>

				<div class="stats-row">
					<div class="stats-label">Логистика</div>
					<div class="stats-value">
						<span>{{ formatValue(stats.logistics) }} ₽</span>
					</div>
				</div>

				<div class="stats-row">
					<div class="stats-label">Хранение</div>
					<div class="stats-value">
						<span>{{ formatValue(stats.storage) }} ₽</span>
					</div>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed } from 'vue';
import { formatFiniteNumber, toFiniteNumber } from '@/utils/safeNumber';

const props = defineProps({
	stats: {
		type: Object,
		default: () => null
	},
	isLoading: {
		type: Boolean,
		default: false
	}
});

// Проверка наличия данных
const hasData = computed(() => {
	return props.stats && Object.keys(props.stats).length > 0;
});

const formatValue = (value) => {
	const numeric = toFiniteNumber(value);
	if (numeric === null) return '-';
	return formatFiniteNumber(numeric, {
		minimumFractionDigits: Number.isInteger(numeric) ? 0 : 2,
		maximumFractionDigits: Number.isInteger(numeric) ? 0 : 2,
		fallback: '-',
	});
};

const formatPercentage = (value) =>
	formatFiniteNumber(value, { maximumFractionDigits: 1, fallback: '-' });
</script>

<style scoped>
.stats-block {
	background: #2d2d2d;
	border-radius: 8px;
	padding: 20px;
	color: #fff;
	box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.stats-header {
	font-size: 24px;
	font-weight: 600;
	margin-bottom: 16px;
	color: #fff;
}

/* Состояние загрузки */
.stats-loading {
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	padding: 20px;
	color: #888;
}

.loading-spinner {
	width: 24px;
	height: 24px;
	border: 3px solid rgba(255, 255, 255, 0.3);
	border-radius: 50%;
	border-top-color: #fff;
	animation: spin 1s linear infinite;
	margin-bottom: 12px;
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
.stats-empty {
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	padding: 20px;
	color: #888;
	text-align: center;
}

.empty-icon {
	font-size: 36px;
	margin-bottom: 12px;
	opacity: 0.6;
}

.empty-text {
	font-size: 16px;
	font-weight: 500;
	margin: 0 0 8px 0;
	color: #fff;
}

.empty-hint {
	font-size: 14px;
	color: #aaa;
	max-width: 300px;
}

/* Основные данные */
.stats-grid {
	display: grid;
	grid-template-columns: repeat(2, 1fr);
	grid-auto-flow: row;
	gap: 16px;
	padding: 4px;
}

.stats-group {
	display: grid;
	grid-template-columns: 1fr;
	gap: 10px;
	background: rgba(255, 255, 255, 0.03);
	border: 1px solid rgba(255, 255, 255, 0.08);
	border-radius: 12px;
	padding: 16px;
	transition: all 0.2s ease;
}

.stats-group:hover {
	background: rgba(255, 255, 255, 0.05);
	border-color: rgba(255, 255, 255, 0.12);
}

/* Третья группа на всю ширину */
.stats-group:last-child {
	grid-column: 1 / -1;
	background: rgba(255, 255, 255, 0.04);
	border-color: rgba(255, 255, 255, 0.1);
}

.stats-row {
	display: grid;
	grid-template-columns: 1fr 1fr;
	align-items: center;
	padding: 10px 0;
	border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.stats-row:last-child {
	border-bottom: none;
}

.stats-label {
	color: #999;
	font-size: 13px;
	font-weight: 500;
	text-align: left;
	line-height: 1.4;
	word-break: break-word;
	opacity: 0.9;
}

.stats-value {
	display: flex;
	align-items: center;
	justify-content: flex-end;
	gap: 10px;
	font-size: 14px;
	color: #fff;
	text-align: right;
	line-height: 1.4;
	font-weight: 500;
}

.stats-value span {
	display: block;
	text-align: right;
}

.stats-value--red {
	color: #ff6b6b;
	font-weight: 600;
}

.stats-percentage {
	color: #666;
	font-size: 11px;
	font-weight: 500;
	background: rgba(255, 255, 255, 0.05);
	padding: 2px 6px;
	border-radius: 4px;
}

.stats-secondary {
	color: #777;
	font-size: 12px;
	font-weight: 400;
}

.stats-icon {
	color: #666;
	font-size: 16px;
}

/* Заголовок для групп (опционально) */
.stats-group::before {
	content: '';
	display: block;
	height: 3px;
	background: linear-gradient(90deg, rgba(255, 107, 107, 0.6), transparent);
	border-radius: 2px;
	margin-bottom: 8px;
}

.stats-group:last-child::before {
	background: linear-gradient(90deg, rgba(100, 200, 100, 0.6), transparent);
}
</style>