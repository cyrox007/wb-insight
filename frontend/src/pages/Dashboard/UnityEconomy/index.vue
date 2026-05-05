<script setup>
import { ref, computed, onMounted } from 'vue'
import UnityEconomyService from '@/API/Dashboard/UnityEconomyService'
import UnitEconomyBlock from '@/components/Widgets/UnitEconomyBlock.vue'
import BaseCarts from '@/components/Diagrams/BaseCarts.vue'
import UnitEconomyTable from '@/components/Widgets/UnitEconomyTable.vue'
import { notify } from '@/composables/notification'

const isLoading = ref(true)
const unityData = ref(null)
const tableData = ref([])

// Данные для блоков
const block1Rows = computed(() => {
	if (!unityData.value) return []
	
	const d = unityData.value
	
	return [
		{ label: 'Продажа', value: d.sales_with_spp, type: 'currency' },
		{ label: '', value: null, divider: true },
		{ label: 'Вознаграждение WB', value: d.wb_commission_percent, type: 'percent' },
		{ label: '', value: d.wb_commission_amount, type: 'currency', highlight: true },
		{ label: 'К перечислению продавцу', value: d.to_pay_seller, type: 'currency', highlight: true },
		{ label: '', value: null, divider: true },
		{ label: 'Логистика', value: d.logistics, type: 'currency' },
		{ label: 'Хранение', value: d.storage, type: 'currency' },
		{ label: 'Прочие удержания', value: d.other_deductions, type: 'currency' },
		{ label: 'Штрафы', value: d.fines, type: 'currency' },
		{ label: 'Платная приемка', value: d.paid_acceptance, type: 'currency' },
		{ label: 'Итого к оплате', value: d.total_to_pay, type: 'currency', highlight: true }
	]
})

const block2Rows = computed(() => {
	if (!unityData.value) return []
	
	const d = unityData.value
	
	return [
		{ label: 'Средняя Стоимость продажи', value: d.avg_sale_price, type: 'currency' },
		{ label: 'Налог', value: d.tax, type: 'currency' },
		{ label: '', value: null, divider: true },
		{ label: 'Прочие расходы', value: d.other_expenses, type: 'currency' },
		{ label: 'ДРР', value: d.drr, type: 'percent' },
		{ label: '', value: null, divider: true },
		{ label: 'Себестоимость', value: d.cost_price, type: 'currency' },
		{ label: '', value: null, divider: true },
		{ label: 'Маржинальность', value: d.marginality, type: 'percent', highlight: true },
		{ label: 'Рентабельность', value: d.profitability, type: 'percent', highlight: true },
		{ label: 'Прибыль единицы', value: d.profit_per_unit, type: 'currency', positive: true },
		{ label: 'Прибыль', value: d.profit, type: 'currency', positive: true }
	]
})

// Данные для графика
const chartMetrics = [
	{ key: 'to_pay_accumulated', name: 'Накопилось к выплате', color: '#ff6b6b', visible: true, type: 'rub' },
	{ key: 'fines', name: 'Штраф', color: '#f44336', visible: true, type: 'rub' },
	{ key: 'other_deductions', name: 'Прочие удержания', color: '#ff9800', visible: true, type: 'rub' },
	{ key: 'paid_acceptance', name: 'Платная приемка', color: '#9c27b0', visible: true, type: 'rub' },
	{ key: 'logistics', name: 'Логистика', color: '#2196f3', visible: true, type: 'rub' },
	{ key: 'to_pay_seller', name: 'К перечислению', color: '#4caf50', visible: true, type: 'rub' }
]

const chartData = computed(() => {
	if (!unityData.value || !unityData.value.daily_data) return []
	return unityData.value.daily_data.map(day => ({
		date: day.date,
		to_pay_accumulated: day.to_pay_accumulated,
		fines: day.fines,
		other_deductions: day.other_deductions,
		paid_acceptance: day.paid_acceptance,
		logistics: day.logistics,
		to_pay_seller: day.to_pay_seller
	}))
})

onMounted(async () => {
	isLoading.value = true
	
	try {
		const response = await UnityEconomyService.get_unity_economy_table()
		
		if (response.status === 200) {
			const result = response.data
			
			if (result.status === 'error') {
				notify.error(result.error?.message || 'Ошибка загрузки данных', 3000)
				isLoading.value = false
				return
			}
			
			unityData.value = result.data?.summary || {}
			tableData.value = result.data?.table || []
		}
	} catch (error) {
		console.error('Ошибка загрузки юнит-экономики:', error)
		notify.error('Не удалось загрузить данные юнит-экономики', 3000)
	} finally {
		isLoading.value = false
	}
})
</script>

<template>
	<div class="unity-economy-page">
		<!-- Header с фильтрами -->
		<div class="unity-header">
			<h1 class="page-title">Юнит-экономика</h1>
			<div class="filters">
				<div class="filter-group">
					<label>Артикул</label>
					<input type="text" class="filter-input" placeholder="Выберите артикул..." />
				</div>
				<div class="filter-group">
					<label>Дата от</label>
					<input type="date" class="filter-input" />
				</div>
				<div class="filter-group">
					<label>до</label>
					<input type="date" class="filter-input" />
				</div>
				<button class="filter-btn">Применить</button>
			</div>
		</div>

		<!-- Три блока в ряд -->
		<div class="blocks-container">
			<!-- Блок 1: Финансы -->
			<UnitEconomyBlock 
				title="💰 Финансы и выплаты" 
				:rows="block1Rows" 
				:is-loading="isLoading" 
			/>
			
			<!-- Блок 2: Прибыльность -->
			<UnitEconomyBlock 
				title="📊 Прибыльность" 
				:rows="block2Rows" 
				:is-loading="isLoading" 
			/>
			
			<!-- Блок 3: График -->
			<div class="chart-block">
				<BaseCarts 
					:chart-data="chartData" 
					:metrics="chartMetrics" 
					:is-loading="isLoading" 
				/>
			</div>
		</div>
		
		<!-- Таблица с детализацией по артикулам -->
		<div class="table-container">
			<UnitEconomyTable 
				:data="tableData" 
				:is-loading="isLoading" 
			/>
		</div>
	</div>
</template>

<style scoped>
.unity-economy-page {
	padding: 20px;
	min-height: 100vh;
	background: var(--main-bg);
}

/* Header */
.unity-header {
	display: flex;
	justify-content: space-between;
	align-items: center;
	margin-bottom: 24px;
	padding: 20px;
	background: var(--card-bg);
	border-radius: 12px;
	box-shadow: var(--shadow);
}

.page-title {
	font-size: 28px;
	font-weight: 700;
	color: var(--text-color);
	margin: 0;
}

.filters {
	display: flex;
	gap: 16px;
	align-items: flex-end;
}

.filter-group {
	display: flex;
	flex-direction: column;
	gap: 6px;
}

.filter-group label {
	font-size: 12px;
	color: #999;
	font-weight: 500;
}

.filter-input {
	padding: 10px 14px;
	background: var(--light-bg);
	border: 1px solid var(--border-color);
	border-radius: 6px;
	color: var(--text-color);
	font-size: 14px;
	min-width: 150px;
}

.filter-input:focus {
	outline: none;
	border-color: #ff6b6b;
}

.filter-btn {
	padding: 10px 24px;
	background: linear-gradient(135deg, #ff6b6b, #ff5252);
	color: white;
	border: none;
	border-radius: 6px;
	font-size: 14px;
	font-weight: 600;
	cursor: pointer;
	transition: all 0.2s ease;
	height: 42px;
	align-self: flex-end;
}

.filter-btn:hover {
	transform: translateY(-2px);
	box-shadow: 0 4px 12px rgba(255, 107, 107, 0.4);
}

/* Контейнер блоков */
.blocks-container {
	display: grid;
	grid-template-columns: repeat(3, 1fr);
	gap: 20px;
}

/* Блок с графиком */
.chart-block {
	background: var(--card-bg);
	border-radius: 12px;
	padding: 24px;
	box-shadow: var(--shadow);
	height: fit-content;
}

/* Контейнер таблицы */
.table-container {
	margin-top: 24px;
	background: var(--card-bg);
	border-radius: 12px;
	padding: 24px;
	box-shadow: var(--shadow);
}

/* Адаптивность */
@media screen and (max-width: 1400px) {
	.blocks-container {
		grid-template-columns: repeat(2, 1fr);
	}
	
	.chart-block {
		grid-column: 1 / -1;
	}
}

@media screen and (max-width: 900px) {
	.unity-header {
		flex-direction: column;
		gap: 20px;
		align-items: stretch;
	}
	
	.filters {
		flex-wrap: wrap;
	}
	
	.blocks-container {
		grid-template-columns: 1fr;
	}
}
</style>