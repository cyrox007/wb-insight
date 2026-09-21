<template>
	<div class="unit-economy-block">
		<h2 class="block-title">{{ title }}</h2>
		
		<!-- Состояние загрузки -->
		<div v-if="isLoading" class="block-loading">
			<div class="loading-spinner"></div>
			<p class="loading-text">Загрузка данных...</p>
		</div>

		<!-- Пустое состояние -->
		<div v-else-if="!hasData" class="block-empty">
			<div class="empty-icon">📊</div>
			<p class="empty-text">Нет данных для отображения</p>
		</div>

		<!-- Данные -->
		<div v-else class="block-content">
			<div v-for="(row, index) in rows" :key="index" class="data-row" :class="{ 'row-divider': row.divider }">
				<div class="data-label">{{ row.label }}</div>
				<div class="data-value" :class="getValueClass(row)">
					{{ formatValue(row.value, row.type) }}
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed } from 'vue';
import { formatFiniteNumber, toFiniteNumber } from '@/utils/safeNumber';

const props = defineProps({
	title: {
		type: String,
		required: true
	},
	rows: {
		type: Array,
		default: () => []
	},
	isLoading: {
		type: Boolean,
		default: false
	}
});

const hasData = computed(() => {
	return props.rows && props.rows.length > 0;
});

const formatValue = (value, type = 'currency') => {
	if (value === null || value === undefined || value === '') return '—';
	
	const rawValue = typeof value === 'string' ? value.replace(/[^0-9.-]/g, '') : value;
	const numValue = toFiniteNumber(rawValue);
	if (numValue === null) return '—';

	switch (type) {
		case 'currency':
			return formatFiniteNumber(numValue, {
				minimumFractionDigits: 2,
				maximumFractionDigits: 2,
			}) + ' ₽';
		case 'percent':
			return formatFiniteNumber(numValue, {
				minimumFractionDigits: 2,
				maximumFractionDigits: 2,
			}) + '%';
		case 'number':
			return formatFiniteNumber(numValue, {
				minimumFractionDigits: 0,
				maximumFractionDigits: 2,
			});
		default:
			return value;
	}
};

const getValueClass = (row) => {
	if (row.highlight) return 'data-value--highlight';
	if (row.negative) return 'data-value--negative';
	if (row.positive) return 'data-value--positive';
	return '';
};
</script>

<style scoped>
.unit-economy-block {
	background: var(--card-bg);
	border-radius: 12px;
	padding: 24px;
	box-shadow: var(--shadow);
	height: 100%;
	display: flex;
	flex-direction: column;
}

.block-title {
	font-size: 20px;
	font-weight: 600;
	color: var(--text-color);
	margin-bottom: 20px;
	padding-bottom: 12px;
	border-bottom: 2px solid rgba(255, 107, 107, 0.3);
}

/* Состояние загрузки */
.block-loading {
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	flex: 1;
	padding: 40px 20px;
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
.block-empty {
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	flex: 1;
	padding: 40px 20px;
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

/* Данные */
.block-content {
	display: flex;
	flex-direction: column;
	gap: 8px;
	flex: 1;
}

.data-row {
	display: grid;
	grid-template-columns: 1fr auto;
	align-items: center;
	padding: 10px 0;
	border-bottom: 1px solid rgba(255, 255, 255, 0.05);
	transition: background 0.2s ease;
}

.data-row:last-child {
	border-bottom: none;
}

.data-row:hover {
	background: rgba(255, 255, 255, 0.03);
	padding-left: 8px;
	padding-right: 8px;
	margin-left: -8px;
	margin-right: -8px;
	border-radius: 6px;
}

.data-row-divider {
	margin-top: 12px;
	margin-bottom: 12px;
	border-bottom: 2px solid rgba(255, 255, 255, 0.15) !important;
}

.data-label {
	color: #999;
	font-size: 13px;
	font-weight: 500;
	line-height: 1.4;
}

.data-value {
	font-size: 14px;
	font-weight: 600;
	color: var(--text-color);
	text-align: right;
	white-space: nowrap;
}

.data-value--highlight {
	color: #ff6b6b;
	font-size: 15px;
}

.data-value--positive {
	color: #4caf50;
}

.data-value--negative {
	color: #f44336;
}
</style>
