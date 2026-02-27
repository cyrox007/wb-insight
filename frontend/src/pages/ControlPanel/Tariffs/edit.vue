<script setup>
import CP_Tariffs from '@/API/ControlPanel/CP_Tariffs';
import EditTariffModal from '@/components/TariffModals/edit.vue';
import CreateLimit from '@/components/TariffModals/createLimit.vue';
import EditLimit from '@/components/TariffModals/editLimit.vue';
import ButtonPrimary from '@/components/UI/Buttons/ButtonPrimary.vue';

import { ref, onMounted } from 'vue';
import { useRoute } from 'vue-router';

const route = useRoute();
const isLoaded = ref(false);
const showEditModal = ref(false);
const showAddLimitModal = ref(false);
const showEditLimitModal = ref(false);

const currentTariff = ref({});
const currentLimit = ref(null);
const limits = ref([]);

onMounted(async () => {
	await loadTariff();
});

const getLimitTypeLabel = (type) => {
	const labels = {
		wb_accounts: 'WB аккаунты',
		nm_ids: 'NM ID',
		sync_frequency_hours: 'Частота синхронизации',
		ai_queries_per_month: 'AI-запросы/мес',
		retention_days: 'Хранение данных (дней)'
	}
	return labels[type] || type
}

const openEditLimitModal = (limit) => {
	currentLimit.value = { ...limit };
	showEditLimitModal.value = true;
};

const limitUpdated = () => {
	console.log('fff');

	try {
		loadTariff();
	} catch (error) {
		console.error('Ошибка обновления лимита:', error);
	}
}

const loadTariff = async () => {
	isLoaded.value = true;
	try {
		const response = await CP_Tariffs.getTariff(route.params.id);
		currentTariff.value = response.data.tariff;
		limits.value = response.data.limits;
	} catch (error) {

	}
	isLoaded.value = false;
}

const deleteLimit = async (limitId) => {
	if (!confirm('Удалить лимит? Это действие нельзя отменить.')) return;

	try {
		await CP_Tariffs.deleteLimit(route.params.id, limitId);
		// Обновляем список лимитов
		limits.value = limits.value.filter(l => l.id !== limitId);
	} catch (error) {
		console.error('Ошибка удаления лимита:', error);
		// Можно показать уведомление
	}
};
</script>
<template>
	<div class="tariffs-detail-container" v-if="isLoaded">Loaded...</div>
	<div class="tariffs-detail-container" v-else>
		<div class="tariff-card">
			<div class="tariff-header">
				<div>
					<h1 class="tariff-name">{{ currentTariff.name }}</h1>
					<p class="tariff-code">Код: <code>{{ currentTariff.code }}</code></p>
				</div>
				<div class="tariff-status-badge" :class="{ 'active': currentTariff.is_active }">
					{{ currentTariff.is_active ? 'Активен' : 'Неактивен' }}
				</div>
			</div>
			<div class="tariff-info-grid">
				<div class="info-item">
					<span class="info-label">Цена</span>
					<span class="info-value">{{ currentTariff.price_rub === 0 ? 'Бесплатно' :
						`${currentTariff.price_rub} ₽/мес`
					}}</span>
				</div>
				<div class="info-item">
					<span class="info-label">Создан</span>
					<span class="info-value">{{ new Date(currentTariff.created_at).toLocaleDateString('ru-RU') }}</span>
				</div>
				<div class="info-item">
					<span class="info-label">Обновлён</span>
					<span class="info-value">{{ new Date(currentTariff.updated_at).toLocaleDateString('ru-RU') }}</span>
				</div>
			</div>

			<p class="tariff-description">
				{{ currentTariff.description || 'Описание отсутствует' }}
			</p>

			<div class="tariff-actions">
				<ButtonPrimary @click="showEditModal = true" :text="'Редактировать тариф'" />
			</div>
		</div>
	</div>

	<div class="limits-section">
		<div class="section-header">
			<h2>Лимиты тарифа</h2>
			<!-- <button @click="openAddLimitModal" class="btn btn-primary">+ Добавить лимит</button> -->
			<ButtonPrimary @click="showAddLimitModal = true" :text="'+ Добавить лимит'" />
		</div>

		<div v-if="limits.length === 0" class="empty-limits">
			У этого тарифа пока нет лимитов.
		</div>

		<div v-else class="limits-grid">
			<div v-for="limit in limits" :key="limit.id" class="limit-card">
				<div class="limit-content">
					<div class="limit-type">
						<strong>{{ getLimitTypeLabel(limit.limit_type) }}</strong>
						<code>{{ limit.limit_type }}</code>
					</div>
					<div class="limit-value">
						Значение: <span class="value-number">{{ limit.limit_value }}</span>
					</div>
				</div>
				<div class="limit-actions">
					<button @click="openEditLimitModal(limit)" class="btn-icon" title="Изменить">
						<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"
							width="16" height="16">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
								d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
						</svg>
					</button>
					<button @click="deleteLimit(limit.id)" class="btn-icon delete-btn" title="Удалить">
						<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"
							width="16" height="16">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
								d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M9 7h6" />
						</svg>
					</button>
				</div>
			</div>
		</div>
	</div>

	<!-- Модальные окна (заглушки) -->
	<EditTariffModal :is-open="showEditModal" :current-tariff="currentTariff" @close="showEditModal = false"
		@updated="async () => { await loadTariff() }" />

	<CreateLimit :is-open="showAddLimitModal" :tariff-id="currentTariff.id" @close="showAddLimitModal = false" />

	<EditLimit :is-open="showEditLimitModal" :limit="currentLimit" @close="showEditLimitModal = false"
		@updated="limitUpdated" />
</template>
<style scoped>
.tariff-detail-container {
	padding: 24px;
	max-width: 1200px;
	margin: 0 auto;
}

.tariff-card {
	background-color: var(--card-bg);
	border: 1px solid var(--border-color);
	border-radius: 12px;
	padding: 28px;
	box-shadow: var(--shadow);
	margin-bottom: 32px;
}

.tariff-header {
	display: flex;
	justify-content: space-between;
	align-items: flex-start;
	margin-bottom: 20px;
	flex-wrap: wrap;
	gap: 16px;
}

.tariff-name {
	font-size: 1.75rem;
	font-weight: 700;
	color: var(--text-color);
	margin: 0;
}

.tariff-code {
	font-size: 1rem;
	color: #aaa;
	margin: 8px 0 0 0;
}

.tariff-code code {
	background: var(--medium-bg);
	padding: 2px 6px;
	border-radius: 4px;
	font-family: monospace;
	color: var(--secondary-color);
}

.tariff-status-badge {
	padding: 6px 12px;
	border-radius: 20px;
	font-size: 0.85rem;
	font-weight: 600;
	background-color: rgba(231, 76, 60, 0.2);
	color: var(--accent-color);
}

.tariff-status-badge.active {
	background-color: rgba(46, 204, 113, 0.2);
	color: var(--success-color);
}

.tariff-info-grid {
	display: grid;
	grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
	gap: 16px;
	margin-bottom: 20px;
}

.info-item {
	display: flex;
	flex-direction: column;
}

.info-label {
	font-size: 0.85rem;
	color: #888;
	margin-bottom: 4px;
}

.info-value {
	font-size: 1.1rem;
	font-weight: 600;
	color: var(--text-color);
}

.tariff-description {
	color: #ccc;
	line-height: 1.6;
	margin: 20px 0;
	padding: 16px;
	background: var(--medium-bg);
	border-radius: 8px;
}

.tariff-actions {
	margin-top: 20px;
}

.limits-section {
	background-color: var(--card-bg);
	border: 1px solid var(--border-color);
	border-radius: 12px;
	padding: 24px;
	box-shadow: var(--shadow);
}

.section-header {
	display: flex;
	justify-content: space-between;
	align-items: center;
	margin-bottom: 20px;
	flex-wrap: wrap;
	gap: 16px;
}

.section-header h2 {
	font-size: 1.4rem;
	color: var(--text-color);
	margin: 0;
}

.empty-limits {
	text-align: center;
	color: #888;
	font-style: italic;
	padding: 32px;
}

.limits-grid {
	display: grid;
	gap: 16px;
}

.limit-card {
	display: flex;
	justify-content: space-between;
	align-items: center;
	padding: 16px;
	background-color: var(--medium-bg);
	border-radius: 10px;
	transition: var(--transition);
}

.limit-card:hover {
	background-color: var(--hover-bg);
}

.limit-content {
	flex: 1;
}

.limit-type {
	display: flex;
	gap: 8px;
	align-items: center;
	margin-bottom: 6px;
}

.limit-type code {
	font-family: monospace;
	background: rgba(52, 152, 219, 0.2);
	color: var(--secondary-color);
	padding: 2px 6px;
	border-radius: 4px;
	font-size: 0.85rem;
}

.limit-value {
	color: #bbb;
	font-size: 0.95rem;
}

.value-number {
	font-weight: 600;
	color: var(--text-color);
}

.limit-actions {
	display: flex;
	gap: 8px;
	margin-left: 16px;
}

.btn-icon {
	width: 32px;
	height: 32px;
	border-radius: 6px;
	background-color: var(--light-bg);
	border: 1px solid var(--border-color);
	display: flex;
	align-items: center;
	justify-content: center;
	cursor: pointer;
	transition: var(--transition);
}

.btn-icon:hover {
	background-color: var(--hover-bg);
}

.delete-btn:hover {
	background-color: rgba(231, 76, 60, 0.2);
}
</style>