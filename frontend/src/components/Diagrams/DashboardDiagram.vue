<template>
	<div class="chart-container">
		<div class="chart-header">
			<h2 class="chart-title">Сводные данные по дням</h2>
		</div>

		<!-- Легенда с чекбоксами -->
		<div class="chart-legend">
			<div class="legend-group" v-for="(group, groupIndex) in metricGroups" :key="groupIndex">
				<div class="legend-item" v-for="metric in group" :key="metric.key">
					<input type="checkbox" :id="metric.key" v-model="metric.visible" @change="updateVisibleSeries" />
					<label :for="metric.key" :style="{ color: metric.color }">
						{{ metric.name }}
					</label>
				</div>
			</div>
		</div>

		<!-- Диаграмма -->
		<div v-if="hasData" class="chart-area" ref="chartArea">
			<!-- Левая шкала (рубли) -->
			<div class="axis left">
				<div v-for="value in [1000000, 800000, 600000, 400000, 200000, 0]" :key="value" class="axis-label"
					:style="{ bottom: (value / maxValue) * 100 + '%' }">
					{{ formatRub(value) }}
				</div>
			</div>

			<!-- Правая шкала (проценты) -->
			<div class="axis right">
				<div v-for="value in [100, 80, 60, 40, 20, 0]" :key="value" class="axis-label"
					:style="{ bottom: value + '%' }">
					{{ value }}%
				</div>
			</div>

			<!-- Сетка -->
			<div class="grid">
				<div v-for="i in 5" :key="i" class="grid-line horizontal" :style="{ bottom: (i * 20) + '%' }"></div>
			</div>

			<!-- Контейнер для всех столбиков -->
			<div class="bars-container">
				<!-- Для каждого дня создаем группу столбиков -->
				<div v-for="(day, dayIndex) in chartData" :key="dayIndex" class="day-group"
					:style="{ left: (dayIndex * 100 / (chartData.length - 1)) + '%' }">
					<!-- Столбики рублевых метрик -->
					<div v-for="(metric, mIndex) in rubMetrics" :key="metric.key" class="bar-wrapper" :style="{
						left: (mIndex * 12) + 'px',
						zIndex: metric.visible ? 10 : -1
					}">
						<div v-if="metric.visible" class="bar" :style="{
							height: (day[metric.key] / maxValue) * 100 + '%',
							backgroundColor: metric.color,
							width: '8px'
						}">
							<div class="bar-tooltip">
								<div class="tooltip-label">{{ metric.name }}</div>
								<div class="tooltip-value">{{ formatRub(day[metric.key]) }}</div>
							</div>
						</div>
					</div>

					<!-- Столбики процентных метрик -->
					<div v-for="(metric, mIndex) in percentMetrics" :key="metric.key" class="bar-wrapper" :style="{
						left: ((rubMetrics.length + mIndex) * 12 + 4) + 'px',
						zIndex: metric.visible ? 10 : -1
					}">
						<div v-if="metric.visible" class="bar" :style="{
							height: day[metric.key] + '%',
							backgroundColor: metric.color,
							width: '8px'
						}">
							<div class="bar-tooltip">
								<div class="tooltip-label">{{ metric.name }}</div>
								<div class="tooltip-value">{{ day[metric.key] }}%</div>
							</div>
						</div>
					</div>

					<!-- Подпись даты -->
					<div class="date-label">{{ day.date }}</div>
				</div>
			</div>
		</div>

		<!-- Пустое состояние -->
		<div v-else class="chart-empty">
			📊 Нет данных для отображения
		</div>
	</div>
</template>

<script setup>
import { ref, computed } from 'vue';

// Данные диаграммы
const props = defineProps({
	chartData: {
		type: Array,
		default: () => []
	}
});

// Все метрики
const allMetrics = ref([
	// Рублевые метрики
	{ key: 'orders', name: 'Заказы, руб', color: '#ff9800', visible: true, type: 'rub' },
	{ key: 'buyouts', name: 'Выкупы, руб', color: '#4caf50', visible: true, type: 'rub' },
	{ key: 'profit', name: 'Прибыль, руб', color: '#f44336', visible: true, type: 'rub' },

	// Процентные метрики
	{ key: 'margin', name: 'Маржина, %', color: '#9c27b0', visible: true, type: 'percent' },
	{ key: 'cr', name: 'CR', color: '#ff9800', visible: true, type: 'percent' },
	{ key: 'ctr', name: 'CTR', color: '#e91e63', visible: true, type: 'percent' },
	{ key: 'drr', name: 'ДРР', color: '#607d8b', visible: true, type: 'percent' }
]);

// Группировка для легенды (по 4 элемента в ряд)
const metricGroups = computed(() => {
	const groups = [];
	for (let i = 0; i < allMetrics.value.length; i += 4) {
		groups.push(allMetrics.value.slice(i, i + 4));
	}
	return groups;
});

// Фильтруем метрики по типу
const rubMetrics = computed(() => allMetrics.value.filter(m => m.type === 'rub'));
const percentMetrics = computed(() => allMetrics.value.filter(m => m.type === 'percent'));

// Максимальное значение для шкалы рублей
const maxValue = computed(() => {
	const rubValues = [];
	rubMetrics.value.forEach(metric => {
		props.chartData.forEach(item => {
			if (item[metric.key] > 0) rubValues.push(item[metric.key]);
		});
	});
	return Math.max(...rubValues, 1000000);
});

const hasData = computed(() => props.chartData.length > 0);

// Форматирование рублей
const formatRub = (value) => {
	if (value >= 1000000) {
		return (value / 1000000).toFixed(1) + 'M';
	}
	if (value >= 1000) {
		return (value / 1000).toFixed(0) + 'K';
	}
	return value;
};

const updateVisibleSeries = () => {
	// Просто триггерим обновление
};
</script>

<style scoped>
.chart-container {
	background: #1a1a1a;
	border-radius: 12px;
	padding: 24px;
	color: #fff;
	font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.chart-header {
	margin-bottom: 20px;
}

.chart-title {
	font-size: 18px;
	font-weight: 600;
	margin: 0;
	color: #fff;
}

/* Легенда */
.chart-legend {
	display: flex;
	flex-direction: column;
	gap: 8px;
	margin-bottom: 24px;
}

.legend-group {
	display: flex;
	flex-wrap: wrap;
	gap: 20px;
}

.legend-item {
	display: flex;
	align-items: center;
	gap: 6px;
	font-size: 13px;
}

.legend-item input[type="checkbox"] {
	width: 14px;
	height: 14px;
	cursor: pointer;
	accent-color: #4caf50;
}

.legend-item label {
	cursor: pointer;
	color: #fff;
}

/* Область диаграммы */
.chart-area {
	position: relative;
	height: 400px;
	margin: 10px 0 20px;
	background: #2d2d2d;
	border-radius: 8px;
	padding: 20px 0;
}

/* Оси */
.axis {
	position: absolute;
	top: 20px;
	bottom: 40px;
	width: 50px;
	font-size: 11px;
	color: #888;
	z-index: 2;
}

.axis.left {
	left: 10px;
}

.axis.right {
	right: 10px;
	text-align: right;
}

.axis-label {
	position: absolute;
	transform: translateY(50%);
}

/* Сетка */
.grid {
	position: absolute;
	left: 70px;
	right: 70px;
	top: 20px;
	bottom: 40px;
	pointer-events: none;
	z-index: 1;
}

.grid-line {
	position: absolute;
	left: 0;
	right: 0;
	height: 1px;
	background: rgba(255, 255, 255, 0.1);
}

/* Контейнер для столбиков */
.bars-container {
	position: absolute;
	left: 70px;
	right: 70px;
	top: 20px;
	bottom: 40px;
	z-index: 3;
}

/* Группа столбиков для одного дня */
.day-group {
	position: absolute;
	bottom: 0;
	width: 100px;
	height: 100%;
	transform: translateX(-50%);
}

/* Контейнер для отдельного столбика */
.bar-wrapper {
	position: absolute;
	bottom: 0;
	width: 8px;
	height: 100%;
}

/* Столбик */
.bar {
	position: absolute;
	bottom: 0;
	width: 100%;
	border-radius: 4px 4px 0 0;
	transition: all 0.2s ease;
	cursor: pointer;
	min-height: 2px;
}

.bar:hover {
	filter: brightness(1.2);
	transform: scaleX(1.1);
	z-index: 20;
}

/* Тултип */
.bar-tooltip {
	position: absolute;
	top: -40px;
	left: 50%;
	transform: translateX(-50%);
	background: #333;
	padding: 6px 10px;
	border-radius: 6px;
	font-size: 11px;
	white-space: nowrap;
	opacity: 0;
	transition: opacity 0.2s;
	pointer-events: none;
	z-index: 30;
	box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
	border: 1px solid #444;
}

.bar:hover .bar-tooltip {
	opacity: 1;
}

.tooltip-label {
	color: #aaa;
	font-size: 10px;
	margin-bottom: 2px;
}

.tooltip-value {
	color: #fff;
	font-weight: 600;
	font-size: 12px;
}

/* Подпись даты */
.date-label {
	position: absolute;
	bottom: -25px;
	left: 50%;
	transform: translateX(-50%);
	font-size: 11px;
	color: #888;
	white-space: nowrap;
}

/* Пустое состояние */
.chart-empty {
	height: 300px;
	display: flex;
	align-items: center;
	justify-content: center;
	background: #2d2d2d;
	border-radius: 8px;
	color: #888;
	font-size: 14px;
}
</style>