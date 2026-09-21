<template>
	<div class="abc-analysis">
		<!-- Состояние загрузки -->
		<div v-if="isLoading" class="abc-loading">
			<div class="loading-spinner"></div>
			<p class="loading-text">Анализ данных...</p>
		</div>

		<!-- Пустое состояние -->
		<div v-else-if="!hasData" class="abc-empty">
			<div class="empty-icon">📊</div>
			<p class="empty-text">Нет данных для анализа</p>
			<p class="empty-hint">
				Данные появятся после синхронизации продаж и остатков
			</p>
		</div>

		<!-- Основной контент -->
		<div v-else>
			<div class="abc-header">
				<h2 class="abc-title">ABC Анализ</h2>
				<div class="abc-stats">
					<div class="abc-stat">
						<div class="abc-stat-label">Категория A</div>
						<div class="abc-stat-value">{{ summary.categoryA.percent }}%</div>
						<div class="abc-stat-subtitle">
							{{ summary.categoryA.revenue }}% выручки
						</div>
					</div>
					<div class="abc-stat">
						<div class="abc-stat-label">Категория B</div>
						<div class="abc-stat-value">{{ summary.categoryB.percent }}%</div>
						<div class="abc-stat-subtitle">
							{{ summary.categoryB.revenue }}% выручки
						</div>
					</div>
					<div class="abc-stat">
						<div class="abc-stat-label">Категория C</div>
						<div class="abc-stat-value">{{ summary.categoryC.percent }}%</div>
						<div class="abc-stat-subtitle">
							{{ summary.categoryC.revenue }}% выручки
						</div>
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
						<tr v-for="item in items" :key="item.id">
							<td>
								<div class="product-identifier">
									<div class="avatar">{{ getInitial(item.sellerSku) }}</div>
									{{ item.sellerSku }}
								</div>
							</td>
							<td>{{ item.wbSku || '—' }}</td>
							<td class="currency">{{ formatMoney(item.revenue) }}</td>
							<td class="currency">{{ formatMoney(item.profit) }}</td>
							<td>{{ formatPercent(item.share) }}</td>
							<td>{{ formatPercent(item.cumulativePercent) }}</td>
							<td>
								<span :class="['abc-category', 'abc-category-' + item.category.toLowerCase()]">
									{{ item.category }}
								</span>
							</td>
							<td>
								<div class="table-actions">
									<button class="table-action view" @click="handleAction('view', item)"
										title="Просмотр">
										<i class="fas fa-eye"></i>
									</button>
									<button class="table-action edit" @click="handleAction('edit', item)"
										title="Редактировать">
										<i class="fas fa-edit"></i>
									</button>
									<button class="table-action delete" @click="handleAction('delete', item)"
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
	</div>
</template>

<script>
import { finiteOrZero, formatFiniteNumber } from '@/utils/safeNumber';

export default {
	name: "AbcAnalysis",
	props: {
		// Массив данных для таблицы
		items: {
			type: Array,
			default: () => [],
		},
		// Флаг загрузки
		isLoading: {
			type: Boolean,
			default: false,
		},
		// Флаг наличия данных (можно вычислять внутри, но лучше передать явно)
		hasData: {
			type: Boolean,
			default: false,
		},
	},
	emits: ["view", "edit", "delete"],
	computed: {
		// Вычисляем статистику для верхних карточек на основе переданных items
		summary() {
			if (!this.items.length) {
				return {
					categoryA: { percent: 0, revenue: 0 },
					categoryB: { percent: 0, revenue: 0 },
					categoryC: { percent: 0, revenue: 0 },
				};
			}

			// Пример логики подсчета (заглушка, так как реальные данные могут приходить с бэка)
			// Обычно бэкенд отдает эти цифры сразу, но если нет - считаем тут
			const totalItems = this.items.length;
			const categoryA = this.items.filter((i) => i.category === "A");
			const categoryB = this.items.filter((i) => i.category === "B");
			const categoryC = this.items.filter((i) => i.category === "C");

			// Считаем % от общего количества товаров (или от выручки, зависит от ТЗ)
			// Здесь я сделал % от кол-ва товаров для примера
			const calcPercent = (arr) => Math.round((arr.length / totalItems) * 100);
			const calcRevenueShare = (arr) => {
				const totalRev = this.items.reduce((acc, i) => acc + finiteOrZero(i.revenue), 0);
				const catRev = arr.reduce((acc, i) => acc + finiteOrZero(i.revenue), 0);
				return totalRev > 0 ? Math.round((catRev / totalRev) * 100) : 0;
			};

			return {
				categoryA: { percent: calcPercent(categoryA), revenue: calcRevenueShare(categoryA) },
				categoryB: { percent: calcPercent(categoryB), revenue: calcRevenueShare(categoryB) },
				categoryC: { percent: calcPercent(categoryC), revenue: calcRevenueShare(categoryC) },
			};
		},
	},
	methods: {
		getInitial(str) {
			return str ? str.charAt(0).toUpperCase() : "?";
		},
		formatMoney(value) {
			return formatFiniteNumber(value, { maximumFractionDigits: 2 }) + (formatFiniteNumber(value, { maximumFractionDigits: 2 }) === "—" ? "" : " ₽");
		},
		formatPercent(value) {
			const formatted = formatFiniteNumber(value, { maximumFractionDigits: 1 });
			return formatted === "—" ? formatted : formatted + "%";
		},
		handleAction(type, item) {
			this.$emit(type, item);
		},
	},
};
</script>

<style scoped>
/* Основной контейнер */
.abc-analysis {
	background-color: var(--card-bg, #fff);
	border-radius: 8px;
	padding: 20px;
	box-shadow: var(--shadow, 0 2px 10px rgba(0, 0, 0, 0.05));
	margin-bottom: 20px;
}

/* Состояния загрузки и пустоты */
.abc-loading,
.abc-empty {
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	padding: 40px 20px;
	text-align: center;
	color: var(--text-secondary, #666);
}

.loading-spinner {
	width: 40px;
	height: 40px;
	border: 4px solid var(--border-color, #e0e0e0);
	border-top: 4px solid var(--accent-color, #4a90e2);
	border-radius: 50%;
	animation: spin 1s linear infinite;
	margin-bottom: 15px;
}

@keyframes spin {
	0% {
		transform: rotate(0deg);
	}

	100% {
		transform: rotate(360deg);
	}
}

.empty-icon {
	font-size: 48px;
	margin-bottom: 15px;
	opacity: 0.5;
}

.empty-hint {
	font-size: 13px;
	color: #999;
	margin-top: 5px;
}

/* Хедер и статистика */
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
	color: var(--accent-color, #333);
	letter-spacing: 1px;
	margin: 0;
}

.abc-stats {
	display: flex;
	gap: 15px;
	flex-wrap: wrap;
}

.abc-stat {
	background-color: var(--medium-bg, #f8f9fa);
	padding: 15px 20px;
	border-radius: 6px;
	text-align: center;
	min-width: 120px;
	border: 1px solid var(--border-color, #eee);
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
	color: var(--text-primary, #333);
}

.abc-stat-subtitle {
	font-size: 12px;
	color: #777;
}

/* Таблица */
.abc-table-container {
	overflow-x: auto;
	margin-top: 20px;
	border-radius: 6px;
	border: 1px solid var(--border-color, #e0e0e0);
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
	border-bottom: 1px solid var(--border-color, #e0e0e0);
}

.abc-table th {
	background-color: var(--light-bg, #f5f5f5);
	font-weight: 600;
	font-size: 14px;
	text-transform: uppercase;
	letter-spacing: 0.5px;
	color: #666;
}

.abc-table tr:hover {
	background-color: var(--hover-bg, #fafafa);
}

.abc-table td.currency {
	font-family: 'Courier New', monospace;
	font-weight: 600;
	color: var(--text-primary, #333);
}

.product-identifier {
	display: flex;
	align-items: center;
	gap: 10px;
}

.avatar {
	width: 32px;
	height: 32px;
	background-color: var(--accent-color, #4a90e2);
	color: white;
	border-radius: 50%;
	display: flex;
	align-items: center;
	justify-content: center;
	font-weight: bold;
	font-size: 14px;
}

/* Бейджи категорий */
.abc-category {
	font-weight: bold;
	padding: 4px 8px;
	border-radius: 4px;
	display: inline-block;
	font-size: 12px;
	letter-spacing: 0.5px;
}

.abc-category-a {
	background-color: var(--success-color, #28a745);
	color: white;
}

.abc-category-b {
	background-color: var(--warning-color, #ffc107);
	color: #333;
	/* Темный текст для желтого фона */
}

.abc-category-c {
	background-color: var(--info-color, #17a2b8);
	color: white;
}

/* Кнопки действий */
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
	transition: transform 0.2s;
}

.table-action.view {
	background-color: var(--secondary-color, #6c757d);
	color: white;
}

.table-action.edit {
	background-color: var(--info-color, #17a2b8);
	color: white;
}

.table-action.delete {
	background-color: var(--danger-color, #dc3545);
	color: white;
}

.table-action:hover {
	transform: scale(1.1);
}
</style>