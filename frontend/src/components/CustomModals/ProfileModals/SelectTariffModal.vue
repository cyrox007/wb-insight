<script setup>
import Modal from '@/components/UI/Modal.vue';
import ButtonCancel from '@/components/UI/Buttons/ButtonCancel.vue';
import ButtonPrimary from '@/components/UI/Buttons/ButtonPrimary.vue';
import LegalConsentChecklist from '@/components/LegalConsentChecklist.vue';
import { ref, onMounted, watch } from 'vue';
import ProfileServices from '@/API/Dashboard/ProfileServices';
import TariffService from '@/API/Dashboard/TariffService';
import { notify } from '@/composables/notification';

const props = defineProps({
	isOpen: Boolean,
	currentTariffCode: String
});

const emit = defineEmits(['close', 'select', 'payment']);
const tariffs = ref([]);
const selectedTariff = ref(props.currentTariffCode || '');
const loadingPayment = ref(false);
const paymentAttemptKey = ref(null);
const legalConsents = ref([]);
const legalValid = ref(false);

const newAttemptKey = () => {
	if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
	return `payment-${Date.now()}-${Math.random().toString(16).slice(2)}`;
};

onMounted(async () => {
	await loadTariffs();
});

watch(
	() => props.currentTariffCode,
	(val) => {
		selectedTariff.value = val || '';
		paymentAttemptKey.value = null;
	},
	{ immediate: true }
);

watch(selectedTariff, () => {
	paymentAttemptKey.value = null;
});

const loadTariffs = async () => {
	try {
		const response = await ProfileServices.get_tariffs();
		tariffs.value = response.data?.tariffs || [];
	} catch (e) {
		console.error('Ошибка загрузки тарифов', e);
		tariffs.value = [];
	}
};

const selectTariff = async () => {
	if (!selectedTariff.value || loadingPayment.value || !legalValid.value) return;

	loadingPayment.value = true;
	paymentAttemptKey.value ||= newAttemptKey();

	try {
		const response = await TariffService.createPayment(
			selectedTariff.value,
			paymentAttemptKey.value,
			legalConsents.value
		);
		const data = response.data;

		if (data.status === 'error') {
			notify.error(data.error.message);
			return;
		}

		if (data.confirmation_url) {
			window.location.assign(data.confirmation_url);
			return;
		}

		if (data.payment_id) {
			emit('payment', data.payment_id);
			return;
		}

		notify.error('Платёжный провайдер не вернул ссылку на оплату');
	} catch (error) {
		notify.error(error.response?.data?.error?.message || 'Не удалось создать платёж');
	} finally {
		loadingPayment.value = false;
	}
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
			<LegalConsentChecklist
				v-model="legalConsents"
				context="billing"
				@valid="legalValid = $event"
			/>
		</template>
		<template #footer>
			<ButtonCancel @click="$emit('close')" text="Отмена" />
			<ButtonPrimary
				@click="selectTariff"
				:disabled="!selectedTariff || !legalValid"
				text="Перейти к оплате"
				:loading="loadingPayment"
			/>
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