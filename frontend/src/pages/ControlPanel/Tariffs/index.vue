<script setup>
import CP_Main from '@/API/ControlPanel/CP_Main';
import ButtonPrimary from '@/components/UI/Buttons/ButtonPrimary.vue';
import CreateTariffModal from '@/components/TariffModals/create.vue';
import Modal from '@/components/UI/Modal.vue';
import { ref, onMounted } from 'vue';
import CP_Tariffs from '@/API/ControlPanel/CP_Tariffs';

const tariffsList = ref([]);
const isLoading = ref(false);

const showCreateModal = ref(false)

const confirmDialog = ref({
	isOpen: false,
	title: '',
	message: '',
	onConfirm: null
})

onMounted(async () => {
	await loadTariffs();
})

async function loadTariffs() {
	isLoading.value = true
	try {
		const { data } = await CP_Tariffs.getTariffList()
		tariffsList.value = data.data.tariffs
	} catch (error) {
		console.error('Ошибка загрузки тарифов:', error)
		// Здесь можно показать уведомление
	} finally {
		isLoading.value = false
	}
}

const toggleActive = (tariff) => {
	// console.log('Изменить статус:', tariff.id, !tariff.is_active)
	const newStatus = !tariff.is_active;
	const action = newStatus ? 'активировать' : 'деактивировать';

	confirmDialog.value = {
		isOpen: true,
		title: 'Подтверждение действия',
		message: `Вы действительно хотите ${action} тариф «${tariff.name}»?`,
		onConfirm: async () => {
			try {
				// Ваш API-вызов
				await CP_Tariffs.updateTariffStatus(tariff.id, newStatus);
				// Обновите список
				await loadTariffs();
			} catch (error) {
				console.error('Ошибка:', error);
				// Можно показать уведомление
			}
		}
	};
}

async function handleConfirm() {
	if (confirmDialog.value.onConfirm) {
		await confirmDialog.value.onConfirm();
	}
	confirmDialog.value.isOpen = false;
}
</script>

<template>
	<div class="tariffs-container">
		<div class="header-actions">
			<h2 class="page-title">Тарифные планы</h2>
			<ButtonPrimary @click="showCreateModal = true" text="+ Создать тариф" />
		</div>

		<CreateTariffModal :is-open="showCreateModal" @close="showCreateModal = false" @created="loadTariffs" />

		<div v-if="isLoading" class="loading-state">
			Загрузка тарифов...
		</div>

		<div v-else-if="tariffsList.length === 0" class="empty-state">
			Нет ни одного тарифного плана.
		</div>

		<div v-else class="tariffs-grid">
			<div v-for="tariff in tariffsList" :key="tariff.id" class="tariff-card"
				:class="{ 'tariff-inactive': !tariff.is_active }">
				<div class="tariff-header">
					<h3 class="tariff-name">{{ tariff.name }}</h3>
					<span class="tariff-code">{{ tariff.code }}</span>
				</div>

				<p class="tariff-description">
					{{ tariff.description || 'Без описания' }}
				</p>

				<div class="tariff-price">
					{{ tariff.price_rub === 0 ? 'Бесплатно' : `${Number(tariff.price_rub).toFixed(2)} ₽/мес` }}
				</div>

				<div class="tariff-status">
					<span class="status-badge"
						:class="{ 'status-active': tariff.is_active, 'status-inactive': !tariff.is_active }">
						{{ tariff.is_active ? 'Активен' : 'Неактивен' }}
					</span>
				</div>

				<div class="tariff-actions">
					<button @click="$router.push({ name: 'control-panel.edit-tariff', params: { id: tariff.id } })"
						class="btn btn-secondary">
						Редактировать
					</button>
					<button @click="toggleActive(tariff)" class="btn"
						:class="tariff.is_active ? 'btn-warning' : 'btn-success'">
						{{ tariff.is_active ? 'Деактивировать' : 'Активировать' }}
					</button>
				</div>
			</div>
		</div>
	</div>
	<!-- Внизу основного шаблона -->
	<Modal v-if="confirmDialog.isOpen" :is-open="true" @close="confirmDialog.isOpen = false">
		<template #header>
			<h3 class="modal-title">{{ confirmDialog.title }}</h3>
		</template>
		<template #body>
			<p>{{ confirmDialog.message }}</p>
		</template>
		<template #footer>
			<div class="modal-footer">
				<button class="btn btn-secondary" @click="confirmDialog.isOpen = false">
					Отмена
				</button>
				<button class="btn btn-danger" @click="handleConfirm">
					Подтвердить
				</button>
			</div>
		</template>
	</Modal>
</template>

<style scoped>
.tariffs-container {
	padding: 20px;
}

.header-actions {
	display: flex;
	justify-content: space-between;
	align-items: center;
	margin-bottom: 24px;
	flex-wrap: wrap;
	gap: 16px;
}

.page-title {
	color: var(--text-color);
	margin-bottom: 24px;
	font-size: 1.5rem;
}

.loading-state,
.empty-state {
	text-align: center;
	padding: 40px;
	color: #aaa;
	font-style: italic;
}

.tariffs-grid {
	display: grid;
	grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
	gap: 20px;
}

.tariff-card {
	background-color: var(--card-bg);
	border: 1px solid var(--border-color);
	border-radius: 12px;
	padding: 20px;
	box-shadow: var(--shadow);
	transition: var(--transition);
}

.tariff-inactive {
	opacity: 0.7;
	border-color: #555;
}

.tariff-header {
	display: flex;
	justify-content: space-between;
	align-items: flex-start;
	margin-bottom: 12px;
}

.tariff-name {
	font-size: 1.25rem;
	font-weight: 600;
	color: var(--text-color);
	margin: 0;
}

.tariff-code {
	background-color: var(--medium-bg);
	color: var(--secondary-color);
	padding: 4px 8px;
	border-radius: 4px;
	font-size: 0.85rem;
	font-family: monospace;
}

.tariff-description {
	color: #ccc;
	font-size: 0.95rem;
	margin-bottom: 16px;
	line-height: 1.5;
}

.tariff-price {
	font-size: 1.4rem;
	font-weight: 700;
	color: var(--success-color);
	margin-bottom: 16px;
}

.tariff-status {
	margin-bottom: 16px;
}

.status-badge {
	padding: 4px 10px;
	border-radius: 20px;
	font-size: 0.85rem;
	font-weight: 600;
}

.status-active {
	background-color: rgba(46, 204, 113, 0.2);
	color: var(--success-color);
}

.status-inactive {
	background-color: rgba(231, 76, 60, 0.2);
	color: var(--accent-color);
}

.tariff-actions {
	display: flex;
	gap: 10px;
	flex-wrap: wrap;
}

.btn {
	flex: 1;
	min-width: 100px;
	padding: 8px 12px;
	border: none;
	border-radius: 6px;
	font-weight: 500;
	cursor: pointer;
	transition: var(--transition);
}

.btn-secondary {
	background-color: var(--secondary-color);
	color: white;
}

.btn-secondary:hover {
	background-color: #2980b9;
}

.btn-success {
	background-color: var(--success-color);
	color: white;
}

.btn-success:hover {
	background-color: #27ae60;
}

.btn-warning {
	background-color: var(--accent-color);
	color: white;
}

.btn-warning:hover {
	background-color: #c0392b;
}

/* Адаптивность */
@media (max-width: 600px) {
	.tariffs-grid {
		grid-template-columns: 1fr;
	}

	.tariff-actions {
		flex-direction: column;
	}

	.btn {
		width: 100%;
	}
}

.btn-danger {
	background-color: var(--accent-color);
	color: white;
}

.btn-danger:hover {
	background-color: #c0392b;
}
</style>