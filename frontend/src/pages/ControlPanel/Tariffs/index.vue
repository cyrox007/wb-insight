<script setup>
import BaseButton from '@/components/UI/Buttons/BaseButton.vue'
import CreateTariffModal from '@/components/TariffModals/create.vue'
import Modal from '@/components/UI/Modal.vue'
import { onMounted, ref } from 'vue'
import CP_Tariffs from '@/API/ControlPanel/CP_Tariffs'

const tariffsList = ref([])
const isLoading = ref(false)
const loadError = ref('')
const actionLoading = ref(false)
const showCreateModal = ref(false)

const confirmDialog = ref({
	isOpen: false,
	title: '',
	message: '',
	onConfirm: null
})

onMounted(loadTariffs)

async function loadTariffs() {
	isLoading.value = true
	loadError.value = ''
	try {
		const { data } = await CP_Tariffs.getTariffList()
		if (data?.status !== 'success' || !Array.isArray(data?.tariffs)) {
			throw new Error('Некорректный ответ API тарифов')
		}
		tariffsList.value = data.tariffs
	} catch (error) {
		console.error('Ошибка загрузки тарифов:', error)
		tariffsList.value = []
		loadError.value = 'Не удалось загрузить тарифные планы. Проверьте API панели управления.'
	} finally {
		isLoading.value = false
	}
}

function closeConfirm() {
	if (actionLoading.value) return
	confirmDialog.value = { isOpen: false, title: '', message: '', onConfirm: null }
}

function toggleActive(tariff) {
	if (actionLoading.value) return
	const newStatus = !tariff.is_active
	const action = newStatus ? 'активировать' : 'деактивировать'

	confirmDialog.value = {
		isOpen: true,
		title: newStatus ? 'Активировать тариф' : 'Деактивировать тариф',
		message: `Вы действительно хотите ${action} тариф «${tariff.name}»?`,
		onConfirm: async () => {
			const response = await CP_Tariffs.updateTariffStatus(tariff.id, newStatus)
			if (response.data?.status !== 'success') {
				throw new Error(response.data?.message || 'Не удалось изменить статус тарифа')
			}
			await loadTariffs()
		}
	}
}

async function handleConfirm() {
	if (actionLoading.value || !confirmDialog.value.onConfirm) return
	actionLoading.value = true
	try {
		await confirmDialog.value.onConfirm()
		confirmDialog.value = { isOpen: false, title: '', message: '', onConfirm: null }
	} catch (error) {
		console.error('Ошибка изменения статуса тарифа:', error)
		loadError.value = error.response?.data?.error?.message || error.message || 'Не удалось изменить статус тарифа.'
		confirmDialog.value = { isOpen: false, title: '', message: '', onConfirm: null }
	} finally {
		actionLoading.value = false
	}
}
</script>

<template>
	<section class="cp-page">
		<header class="cp-page-header">
			<div>
				<p class="cp-eyebrow">Монетизация</p>
				<h2 class="cp-detail-title">Тарифные планы</h2>
				<p class="cp-subtitle">Управление стоимостью, доступностью и продуктовой конфигурацией тарифов.</p>
			</div>
			<BaseButton variant="primary" text="Создать тариф" :disabled="actionLoading" @click="showCreateModal = true" />
		</header>

		<div v-if="isLoading" class="cp-state" role="status">Загружаем тарифы…</div>

		<div v-else-if="loadError" class="cp-state cp-state--error" role="alert">
			<div class="cp-state__stack">
				<strong>{{ loadError }}</strong>
				<BaseButton variant="outline" size="small" text="Повторить" @click="loadTariffs" />
			</div>
		</div>

		<div v-else-if="tariffsList.length === 0" class="cp-state">
			<div class="cp-state__stack">
				<strong>Тарифов пока нет.</strong>
				<span>Создайте первый тарифный план, чтобы настроить доступ к продукту.</span>
				<BaseButton variant="primary" size="small" text="Создать тариф" @click="showCreateModal = true" />
			</div>
		</div>

		<div v-else class="cp-tariff-grid">
			<article
				v-for="tariff in tariffsList"
				:key="tariff.id"
				class="cp-card cp-tariff-card"
				:class="{ 'cp-tariff-card--inactive': !tariff.is_active }"
			>
				<div class="cp-tariff-card__head">
					<div>
						<p class="cp-eyebrow">Тариф</p>
						<h3 class="cp-tariff-card__name">{{ tariff.name }}</h3>
					</div>
					<code class="cp-code">{{ tariff.code }}</code>
				</div>

				<p class="cp-tariff-card__description">{{ tariff.description || 'Описание не добавлено.' }}</p>
				<div class="cp-price">{{ Number(tariff.price_rub) === 0 ? 'Бесплатно' : `${Number(tariff.price_rub).toLocaleString('ru-RU')} ₽/мес` }}</div>

				<div class="cp-tariff-card__footer">
					<div class="cp-chip-row">
						<span class="cp-chip" :class="tariff.is_active ? 'cp-chip--active' : 'cp-chip--inactive'">{{ tariff.is_active ? 'Активен' : 'Неактивен' }}</span>
					</div>
					<div class="cp-divider"></div>
					<div class="cp-actions">
						<BaseButton variant="outline" size="small" text="Редактировать" :disabled="actionLoading" @click="$router.push({ name: 'control-panel.edit-tariff', params: { id: tariff.id } })" />
						<BaseButton :variant="tariff.is_active ? 'danger' : 'success'" size="small" :text="tariff.is_active ? 'Деактивировать' : 'Активировать'" :disabled="actionLoading" @click="toggleActive(tariff)" />
					</div>
				</div>
			</article>
		</div>

		<CreateTariffModal :is-open="showCreateModal" @close="showCreateModal = false" @created="loadTariffs" />

		<Modal
			v-if="confirmDialog.isOpen"
			:is-open="true"
			aria-label="Подтверждение изменения статуса тарифа"
			:close-on-overlay-click="!actionLoading"
			:close-on-escape="!actionLoading"
			@close="closeConfirm"
		>
			<template #header><h3 class="cp-modal-title">{{ confirmDialog.title }}</h3></template>
			<template #body><p class="cp-modal-copy">{{ confirmDialog.message }}</p></template>
			<template #footer>
				<div class="cp-modal-footer">
					<BaseButton variant="outline" text="Отмена" :disabled="actionLoading" @click="closeConfirm" />
					<BaseButton variant="danger" text="Подтвердить" loading-text="Сохраняем…" :loading="actionLoading" @click="handleConfirm" />
				</div>
			</template>
		</Modal>
	</section>
</template>
