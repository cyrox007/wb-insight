<script setup>
import { ref, computed } from 'vue'
const props = defineProps({
	chartData: {
		type: Array,
		default: () => []
	},
	metrics: {
		type: Array,
		default: () => []
	}
});

const hasData = computed(() => props.chartData.length > 0);
const getMaxAbsValue = computed(() => {
	const values = props.chartData.flatMap(item =>
		props.metrics.map(metric => item[metric.key])
	);
	return Math.max(...values);
});

const getMinAbsValue = computed(() => {
	const values = props.chartData.flatMap(item =>
		props.metrics.map(metric => item[metric.key])
	);
	console.log(values);

	return Math.min(...values);
});

// Положительные значения (от 0 до max)
const positiveSteps = computed(() => {
	const step = getMaxAbsValue.value / 5;
	return [5, 4, 3, 2, 1, 0].map(i => step * i);
});

// Отрицательные значения (от 0 до min)  
const negativeSteps = computed(() => {
	const step = Math.abs(getMinAbsValue.value) / 5; // Используем абсолютное значение
	return [1, 2, 3, 4, 5].map(i => -(step * i)); // Отрицательные числа
});

// Все шаги для оси
const axisSteps = computed(() => {
	const min = getMinAbsValue.value;
	const max = getMaxAbsValue.value;
	const hasNegative = min < 0;

	if (!hasNegative) {
		const step = max / 5;
		return [0, 1, 2, 3, 4, 5].map(i => step * i);
	}

	// Симметричная ось
	const maxAbs = Math.max(Math.abs(min), max);

	// Округляем 
	const magnitude = Math.pow(10, Math.floor(Math.log10(maxAbs)));
	const niceMax = Math.ceil(maxAbs / magnitude) * magnitude;

	const steps = [];
	const divisions = 5;

	for (let i = -divisions; i <= divisions; i++) {
		steps.push((niceMax / divisions) * i);
	}

	return steps;
});

// Позиция дня в процентах
const getDayPosition = (index) => {
	if (props.chartData.length <= 1) return 50;
	return (index / (props.chartData.length - 1)) * 100;
};

const getBarStyles = (value, color) => {
	const heightPercent = (Math.abs(value) / getMaxAbsValue.value) * 50; // 50% от половины оси

	if (value >= 0) {
		// Положительные: от центра вверх
		return {
			height: heightPercent + '%',
			backgroundColor: color,
			bottom: '50%', // стартуем от центра
			top: 'auto',
			borderRadius: '4px 4px 0 0'
		};
	} else {
		// Отрицательные: от центра вниз
		return {
			height: heightPercent + '%',
			backgroundColor: color,
			top: '50%', // стартуем от центра
			bottom: 'auto',
			borderRadius: '0 0 4px 4px'
		};
	}
};
</script>
<template>
	<div class="chart-container">
		<div class="chart-header">
			<h2 class="chart-title">Сводные данные по дням</h2>
		</div>
		<!-- Легенда с чекбоксами -->
		<div class="chart-controls">
			<div class="chart-controls--item" v-for="metric in props.metrics" :key="metric.key">
				<input type="checkbox" :id="metric.key" v-model="metric.visible" @change="updateVisibleSeries" />
				<label :for="metric.key" :style="{ color: metric.color }">
					{{ metric.name }}
				</label>
			</div>
		</div>

		<!-- Пустое состояние -->
		<div v-if="!hasData" class="chart-empty">
			<div class="empty-icon">📊</div>
			<p class="empty-text">Нет данных для отображения</p>
			<p class="empty-hint">Данные появятся после синхронизации с Wildberries</p>
		</div>
		<!-- Диаграмма -->
		<div v-else class="chars-area">
			<!-- Ось Y (рубли) -->
			<div class="axis left">
				<div v-for="value in axisSteps" :key="value" class="axis-label" :class="{
					positive: value > 0,
					negative: value < 0,
					zero: value === 0
				}" :style="{
					bottom: (50 + (value / getMaxAbsValue) * 50) + '%'
				}">
					{{ value > 0 ? '+' + value.toFixed(1) : value.toFixed(1) }}
				</div>
			</div>

			<!-- Сетка -->
			<div class="grid">
				<div v-for="i in 5" :key="i" class="grid-line" :style="{ bottom: (i * 20) + '%' }"></div>
			</div>

			<!-- Столбцы -->
			<div class="bars-container">
				<div v-for="(day, dayIndex) in chartData" :key="dayIndex" class="day-group"
					:style="{ left: getDayPosition(dayIndex) + '%' }">
					<div v-for="(metric, mIndex) in metrics" :key="metric.key" class="bar-wrapper" :style="{
						left: (mIndex * 12) + 'px'
					}">
						<div v-if="metric.visible && day[metric.key] != null" class="bar"
							:class="{ positive: day[metric.key] >= 0, negative: day[metric.key] < 0 }"
							:style="getBarStyles(day[metric.key], metric.color)">
							<div class="bar-tooltip" :class="{ 'tooltip-bottom': day[metric.key] < 0 }">
								<div class="tooltip-label">{{ metric.name }}</div>
								<div class="tooltip-value">{{ day[metric.key] }}</div>
							</div>
						</div>
					</div>
					<div class="date-label">{{ day.date || '—' }}</div>
				</div>
			</div>
		</div>
	</div>
</template>

<style scoped>
/* Основные стили */
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
	font-size: 24px;
	font-weight: 600;
}

/* Легенда */
.chart-controls {
	display: flex;
	gap: 10px;
	margin: 5px 0;
}

.chart-controls--item {
	display: flex;
	align-items: center;
	gap: 8px;
	font-size: 13px;
}

.chart-controls--item input[type="checkbox"] {
	width: 16px;
	height: 16px;
	cursor: pointer;
	accent-color: #4caf50;
}

.chart-controls--item label {
	cursor: pointer;
	color: var(--text-color);
}

/* Пустое состояние */
.chart-empty {
	height: 300px;
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	background-color: var(--medium-bg);
	border-radius: 10px;
	color: #888;
	border: 1px dashed var(--border-color);
}

.empty-icon {
	font-size: 48px;
	margin-bottom: 16px;
	opacity: 0.6;
}

.empty-text {
	font-size: 16px;
	font-weight: 500;
	margin: 0 0 8px 0;
	color: var(--text-color);
}

.empty-hint {
	font-size: 14px;
	color: #aaa;
	text-align: center;
	max-width: 300px;
}

/* Область диаграммы */
.chars-area {
	position: relative;
	height: 280px;
	background-color: var(--medium-bg);
	border-radius: 10px;
	padding: 20px 0 30px 60px;
}

/* Оси */
.axis {
	position: absolute;
	top: 20px;
	bottom: 30px;
	width: 50px;
	font-size: 11px;
	color: #888;
	z-index: 2;
	pointer-events: none;
}

.axis.left {
	left: 10px;
}

.axis-label {
	position: absolute;
	transform: translateY(50%);
	width: 100%;
	text-align: right;
}

/* Сетка */
.grid {
	position: absolute;
	left: 60px;
	right: 20px;
	top: 20px;
	bottom: 30px;
	pointer-events: none;
	z-index: 1;
}

.grid-line {
	position: absolute;
	left: 0;
	right: 0;
	height: 1px;
	background: linear-gradient(to right, transparent, rgba(255, 255, 255, 0.1), transparent);
}

/* Столбцы */
.bars-container {
	position: absolute;
	left: 90px;
	right: 30px;
	top: 20px;
	bottom: 30px;
	z-index: 3;
}

.day-group {
	position: absolute;
	bottom: 0;
	width: 40px;
	height: 100%;
	transform: translateX(-50%);
}

.bar-wrapper {
	position: absolute;
	bottom: 0;
	width: 8px;
	height: 100%;
}

.bar {
	position: absolute;
	width: 100%;
	transition: all 0.2s ease;
	cursor: pointer;
	min-height: 2px;
}

.bar:hover {
	filter: brightness(1.2);
	transform: scaleX(1.1);
	z-index: 20;
}

/* Тултипы для столбцов */
.bar-tooltip {
	position: absolute;
	left: 50%;
	transform: translateX(-50%);
	background: rgba(30, 30, 40, 0.95);
	padding: 6px 10px;
	border-radius: 6px;
	font-size: 12px;
	white-space: nowrap;
	opacity: 0;
	transition: opacity 0.2s;
	pointer-events: none;
	z-index: 30;
	border: 1px solid var(--border-color);
}

.bar-tooltip:not(.tooltip-bottom) {
	bottom: 100%;
	margin-bottom: 8px;
}

.bar-tooltip.tooltip-bottom {
	top: 100%;
	margin-top: 8px;
}

.bar:hover .bar-tooltip {
	opacity: 1;
}

/* Подписи дат */
.date-label {
	position: absolute;
	bottom: -25px;
	left: 50%;
	transform: translateX(-50%);
	font-size: 11px;
	color: #aaa;
	white-space: nowrap;
	z-index: 5;
}

.date-labels-container {
	position: absolute;
	left: 60px;
	right: 20px;
	bottom: 0;
	height: 30px;
	z-index: 5;
}

.date-label-wrapper {
	position: absolute;
	bottom: 0;
	transform: translateX(-50%);
	font-size: 11px;
	color: #aaa;
	white-space: nowrap;
}
</style>