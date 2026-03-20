<template>
	<div class="warehouse-chart">
		<h3 class="chart-title">Продажи со складов и остаток</h3>

		<div v-if="isLoading" class="chart-loading">
			<div class="loading-spinner"></div>
			<p class="loading-text">Загрузка данных...</p>
		</div>

		<!-- Пустое состояние -->
		<div v-else-if="!hasData" class="chart-empty">
			<div class="empty-icon">📦</div>
			<p class="empty-text">Нет данных для отображения</p>
			<p class="empty-hint">
				Данные появятся после синхронизации складских остатков
			</p>
		</div>
		<div v-else class="chart-container">
			<!-- Chart bars -->
			<div v-for="(warehouse, index) in warehouses" :key="warehouse.name" class="chart-row"
				@mouseenter="showTooltip(warehouse, index)" @mouseleave="hideTooltip" @mousemove="moveTooltip">
				<div class="warehouse-name">{{ warehouse.name }}</div>
				<div class="bars-wrapper">
					<div class="bar-container">
						<div class="bar bar-sum" :style="{ width: getBarWidth(warehouse.sum, maxValue) + '%' }"></div>
						<div class="bar bar-stock" :style="{ width: getBarWidth(warehouse.stock, maxValue) + '%' }">
						</div>
						<div class="bar bar-goods"
							:style="{ width: getBarWidth(warehouse.goodsAmount, maxValue) + '%' }"></div>
					</div>
					<div class="bar-values">
						<span class="value-sum">{{ warehouse.sum.toLocaleString('ru-RU') }}</span>
						<span class="value-stock">{{ warehouse.stock.toLocaleString('ru-RU') }}</span>
						<span class="value-goods">{{ formatPrice(warehouse.goodsAmount) }}</span>
					</div>
				</div>
			</div>
		</div>

		<!-- Tooltip -->
		<div v-if="tooltip.visible" class="tooltip" :style="tooltipStyle">
			<div class="tooltip-title">{{ tooltip.data?.name }}</div>
			<div class="tooltip-row">
				<span class="tooltip-color sum"></span>
				<span>sum Кол-во: <strong>{{ tooltip.data?.sum }}</strong></span>
			</div>
			<div class="tooltip-row">
				<span class="tooltip-color stock"></span>
				<span>Остаток: <strong>{{ tooltip.data?.stock }}</strong></span>
			</div>
			<div class="tooltip-row">
				<span class="tooltip-color goods"></span>
				<span>Товаров на сумму: <strong>{{ formatPrice(tooltip.data?.goodsAmount || 0) }}</strong></span>
			</div>
		</div>

		<!-- Legend -->
		<div class="legend">
			<div class="legend-item">
				<span class="legend-color sum"></span>
				<span>sum Кол-во</span>
			</div>
			<div class="legend-item">
				<span class="legend-color stock"></span>
				<span>Остаток</span>
			</div>
			<div class="legend-item">
				<span class="legend-color goods"></span>
				<span>Товаров на сумму</span>
			</div>
		</div>
	</div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

const props = defineProps({
	data: {
		type: Array,
		default: () => []
	}
})

const tooltip = ref({
	visible: false,
	data: null,
	x: 0,
	y: 0
})

const tooltipStyle = computed(() => ({
	left: tooltip.value.x + 'px',
	top: tooltip.value.y + 'px'
}))

const maxValue = computed(() => {
	return Math.max(...props.data.map(w => Math.max(w.sum, w.stock, w.goodsAmount)))
})

const getBarWidth = (value, max) => {
	if (max === 0) return 0
	return (value / max) * 100
}

const formatPrice = (value) => {
	return value.toLocaleString('ru-RU') + ' ₽'
}

const showTooltip = (data, index) => {
	tooltip.value = {
		visible: true,
		data,
		x: 0,
		y: 0
	}
}

const hideTooltip = () => {
	tooltip.value.visible = false
}

const moveTooltip = (event) => {
	const tooltipElement = document.querySelector('.tooltip')
	if (tooltipElement) {
		const rect = tooltipElement.getBoundingClientRect()
		const containerRect = (event.currentTarget).getBoundingClientRect()

		let x = event.pageX + 15
		let y = event.pageY + 15

		// Prevent tooltip from going off screen
		if (x + rect.width > window.innerWidth) {
			x = event.pageX - rect.width - 15
		}
		if (y + rect.height > window.innerHeight) {
			y = event.pageY - rect.height - 15
		}

		tooltip.value.x = x
		tooltip.value.y = y
	}
}

// Parse the provided data
const warehouses = computed(() => props.data)
</script>

<style scoped>
.warehouse-chart {
	padding: 16px;
	background: var(--card-bg);
	border-radius: 8px;
	position: relative;
	overflow: hidden;
	border: 1px solid var(--border-color);
}

.chart-title {
	margin: 0 0 16px 0;
	font-size: 16px;
	font-weight: 600;
	color: var(--text-color);
}

.chart-container {
	max-height: 600px;
	overflow-y: auto;
	padding-right: 8px;
}

.chart-row {
	display: flex;
	align-items: center;
	margin-bottom: 8px;
	padding: 8px;
	cursor: pointer;
	transition: var(--transition);
	border-radius: 6px;
}

.chart-row:hover {
	background-color: var(--hover-bg);
}

.warehouse-name {
	width: 120px;
	min-width: 120px;
	font-size: 12px;
	color: var(--text-color);
	padding-right: 8px;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
	opacity: 0.9;
}

.bars-wrapper {
	flex: 1;
	display: flex;
	align-items: center;
	gap: 8px;
}

.bar-container {
	flex: 1;
	height: 20px;
	background: var(--light-bg);
	border-radius: 4px;
	overflow: hidden;
	position: relative;
}

.bar {
	height: 100%;
	position: absolute;
	top: 0;
	left: 0;
	transition: width 0.3s ease;
}

.bar-sum {
	background: var(--success-color);
	z-index: 3;
}

.bar-stock {
	background: var(--warning-color);
	z-index: 2;
	opacity: 0.8;
}

.bar-goods {
	background: #f39c12;
	z-index: 1;
	opacity: 0.6;
}

.bar-values {
	display: flex;
	flex-direction: column;
	gap: 2px;
	min-width: 80px;
}

.value-sum,
.value-stock,
.value-goods {
	font-size: 11px;
	font-weight: 500;
}

.value-sum {
	color: var(--success-color);
}

.value-stock {
	color: var(--warning-color);
}

.value-goods {
	color: var(--warning-color);
}

/* Tooltip */
.tooltip {
	position: fixed;
	background: var(--card-bg);
	border: 1px solid var(--border-color);
	border-radius: 8px;
	padding: 12px;
	box-shadow: var(--shadow);
	z-index: 1000;
	pointer-events: none;
	min-width: 200px;
	color: var(--text-color);
}

.tooltip-title {
	font-weight: 600;
	margin-bottom: 8px;
	padding-bottom: 8px;
	border-bottom: 1px solid var(--border-color);
	font-size: 14px;
}

.tooltip-row {
	display: flex;
	align-items: center;
	gap: 8px;
	margin-bottom: 6px;
	font-size: 12px;
}

.tooltip-row:last-child {
	margin-bottom: 0;
}

.tooltip-color {
	width: 12px;
	height: 12px;
	border-radius: 3px;
	display: inline-block;
}

.tooltip-color.sum {
	background: var(--success-color);
}

.tooltip-color.stock {
	background: var(--warning-color);
}

.tooltip-color.goods {
	background: #f39c12;
}

/* Legend */
.legend {
	display: flex;
	gap: 16px;
	margin-top: 16px;
	padding-top: 12px;
	border-top: 1px solid var(--border-color);
	flex-wrap: wrap;
}

.legend-item {
	display: flex;
	align-items: center;
	gap: 6px;
	font-size: 12px;
	color: var(--text-color);
	opacity: 0.8;
}

.legend-color {
	width: 12px;
	height: 12px;
	border-radius: 3px;
}

.legend-color.sum {
	background: var(--success-color);
}

.legend-color.stock {
	background: var(--warning-color);
}

.legend-color.goods {
	background: #f39c12;
}

/* Scrollbar */
.chart-container::-webkit-scrollbar {
	width: 6px;
}

.chart-container::-webkit-scrollbar-track {
	background: var(--medium-bg);
	border-radius: 3px;
}

.chart-container::-webkit-scrollbar-thumb {
	background: var(--border-color);
	border-radius: 3px;
}

.chart-container::-webkit-scrollbar-thumb:hover {
	background: var(--light-bg);
}

/* Состояния загрузки и пустоты */
.chart-loading,
.chart-empty {
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	padding: 40px 20px;
	text-align: center;
	color: var(--text-color);
	opacity: 0.8;
}

.loading-spinner {
	width: 40px;
	height: 40px;
	border: 4px solid var(--border-color);
	border-top-color: var(--secondary-color);
	border-radius: 50%;
	animation: spin 1s linear infinite;
	margin-bottom: 15px;
}

@keyframes spin {
	to {
		transform: rotate(360deg);
	}
}

.loading-text {
	font-size: 14px;
	color: var(--text-color);
	margin: 0;
}

.empty-icon {
	font-size: 48px;
	margin-bottom: 15px;
	opacity: 0.6;
}

.empty-text {
	font-size: 16px;
	font-weight: 500;
	margin: 0 0 8px 0;
	color: var(--text-color);
}

.empty-hint {
	font-size: 13px;
	color: var(--text-color);
	opacity: 0.6;
	margin: 0;
	max-width: 250px;
	line-height: 1.4;
}
</style>