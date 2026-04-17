<script setup>
import Modal from '@/components/UI/Modal.vue';
import ButtonCancel from '@/components/UI/Buttons/ButtonCancel.vue';
import ButtonPrimary from '@/components/UI/Buttons/ButtonPrimary.vue';
import { ref, onMounted, watch } from 'vue';
import ProfileServices from '@/API/Dashboard/ProfileServices';

const props = defineProps({
	isOpen: Boolean,
	currentTariffCode: String // например, 'demo'
});

const emit = defineEmits(['close', 'select']);

// Мок-данные (замените на API-запрос)
const tariffs = ref([]);

const selectedTariff = ref(props.currentTariffCode || '');

onMounted(async () => {
	// Здесь можно загрузить реальные тарифы через API
	await loadTariffs();
});

watch(
	() => props.currentTariffCode,
	(val) => {
		selectedTariff.value = val || ''
	},
	{ immediate: true }
)

const loadTariffs = async () => {
	try {
		const response = await ProfileServices.get_tariffs();
		tariffs.value = response.data?.tariffs || [];
	} catch (e) {
		console.error('Ошибка загрузки тарифов', e);
		tariffs.value = [];
	}
}

const selectTariff = () => {
	if (!selectedTariff.value) return;
	emit('select', selectedTariff.value);
	emit('close');
};
</script>

<template>
	<Modal :is-open="isOpen" @close="$emit('close')">
		<template #header>
			<h3>Выберите подходящий тариф</h3>
		</template>
		<template #body>
			<div class="tariffs-grid">
				<div v-for="tariff in tariffs" :key="tariff.code" class="tariff-card"
					:class="{ selected: selectedTariff === tariff.code }" @click="selectedTariff = tariff.code">
					<div class="tariff-header">
						<h4 class="tariff-name">{{ tariff.name }}</h4>
						<div class="tariff-price">
							{{ tariff.price_rub === 0 ? 'Бесплатно' : `${tariff.price_rub} ₽/мес` }}
						</div>
					</div>
					<p class="tariff-description">{{ tariff.description }}</p>
					<div v-if="currentTariffCode === tariff.code" class="current-badge">
						Текущий тариф
					</div>
				</div>
			</div>
			<p v-if="!selectedTariff" class="selection-hint">
				Выберите тариф, чтобы продолжить
			</p>
		</template>
		<template #footer>
			<ButtonCancel @click="$emit('close')" text="Отмена" />
			<ButtonPrimary @click="selectTariff" :disabled="!selectedTariff" text="Применить тариф" />
		</template>
	</Modal>
</template>

<style scoped>
.tariffs-grid {
	display: grid;
	grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
	gap: 16px;
	margin-bottom: 16px;
}

.tariff-card {
	background-color: var(--medium-bg);
	border: 1px solid var(--border-color);
	border-radius: 10px;
	padding: 20px;
	cursor: pointer;
	transition: var(--transition);
	position: relative;
}

.tariff-card:hover {
	background-color: var(--hover-bg);
	border-color: var(--secondary-color);
}

.tariff-card.selected {
	border-color: var(--success-color);
	background-color: rgba(46, 204, 113, 0.08);
}

.tariff-header {
	display: flex;
	justify-content: space-between;
	align-items: flex-start;
	margin-bottom: 12px;
}

.tariff-name {
	font-size: 1.1rem;
	font-weight: 600;
	color: var(--text-color);
	margin: 0;
}

.tariff-price {
	font-size: 1.2rem;
	font-weight: 700;
	color: var(--success-color);
}

.tariff-description {
	color: #ccc;
	font-size: 0.95rem;
	line-height: 1.5;
	margin: 0 0 16px 0;
}

.current-badge {
	position: absolute;
	top: 12px;
	right: 12px;
	background-color: rgba(52, 152, 219, 0.2);
	color: var(--secondary-color);
	padding: 4px 8px;
	border-radius: 20px;
	font-size: 0.8rem;
	font-weight: 600;
}

.selection-hint {
	color: #888;
	font-style: italic;
	text-align: center;
	margin-top: 8px;
}
</style>