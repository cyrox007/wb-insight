<script setup>
import CP_Tariffs from '@/API/ControlPanel/CP_Tariffs'
import EditTariffModal from '@/components/TariffModals/edit.vue'
import CreateLimit from '@/components/TariffModals/createLimit.vue'
import EditLimit from '@/components/TariffModals/editLimit.vue'
import BaseButton from '@/components/UI/Buttons/BaseButton.vue'
import Modal from '@/components/UI/Modal.vue'
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const isLoading = ref(false)
const loadError = ref('')
const deleteLoading = ref(false)
const showEditModal = ref(false)
const showAddLimitModal = ref(false)
const showEditLimitModal = ref(false)
const currentTariff = ref(null)
const currentLimit = ref(null)
const limits = ref([])
const deleteConfirm = ref({ isOpen: false, limitType: '', label: '' })
const requiredLimitTypes = new Set(['wb_accounts', 'sync_frequency_hours'])
const isSystemTariff = computed(() => String(currentTariff.value?.code || '').toLowerCase() === 'demo')

const isProtectedLimit = (limit) =>
	Boolean(currentTariff.value?.is_active) && requiredLimitTypes.has(limit?.limit_type)

onMounted(loadTariff)

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

function openEditLimitModal(limit) {
	currentLimit.value = { ...limit }
	showEditLimitModal.value = true
}

function askDeleteLimit(limit) {
	if (isProtectedLimit(limit)) return
	deleteConfirm.value = {
		isOpen: true,
		limitType: limit.limit_type,
		label: getLimitTypeLabel(limit.limit_type)
	}
}

async function loadTariff() {
	isLoading.value = true
	loadError.value = ''
	try {
		const response = await CP_Tariffs.getTariff(route.params.id)
		currentTariff.value = response.data?.tariff || null
		limits.value = response.data?.limits || []
		if (!currentTariff.value) loadError.value = 'Тариф не найден.'
	} catch (error) {
		console.error('Ошибка загрузки тарифа:', error)
		currentTariff.value = null
		loadError.value = 'Не удалось загрузить данные тарифа.'
	} finally {
		isLoading.value = false
	}
}

async function deleteLimitConfirmed() {
	if (!deleteConfirm.value.limitType) return
	deleteLoading.value = true
	try {
		await CP_Tariffs.deleteLimit(route.params.id, deleteConfirm.value.limitType)
		deleteConfirm.value = { isOpen: false, limitType: '', label: '' }
		await loadTariff()
	} catch (error) {
		console.error('Ошибка удаления лимита:', error)
		loadError.value = 'Не удалось удалить лимит.'
		deleteConfirm.value.isOpen = false
	} finally {
		deleteLoading.value = false
	}
}
</script>

<template>
	<section class="cp-page">
		<header class="cp-page-header">
			<div>
				<p class="cp-eyebrow">Тарифы · конфигурация</p>
				<h2 class="cp-detail-title">Настройки тарифа</h2>
				<p class="cp-subtitle">Основные параметры плана и продуктовые ограничения.</p>
			</div>
			<BaseButton variant="outline" size="small" text="← К тарифам" @click="router.push({ name: 'control-panel.tariffs' })" />
		</header>

		<div v-if="isLoading" class="cp-state" role="status">Загружаем тариф…</div>

		<div v-else-if="loadError && !currentTariff" class="cp-state cp-state--error" role="alert">
			<div class="cp-state__stack">
				<strong>{{ loadError }}</strong>
				<BaseButton variant="outline" size="small" text="Повторить" @click="loadTariff" />
			</div>
		</div>

		<template v-else-if="currentTariff">
			<div v-if="isSystemTariff" class="cp-info-callout">
				<strong>Системный тариф demo.</strong>
				<span>Он используется регистрацией, trial-доступом, квотами и планировщиком синхронизации. Его нельзя удалить или деактивировать; цена всегда 0 ₽, а публичность выключена.</span>
			</div>

			<article class="cp-card cp-detail-card">
				<div class="cp-detail-header">
					<div>
						<div class="cp-chip-row">
							<h3 class="cp-detail-title">{{ currentTariff.name }}</h3>
							<span v-if="isSystemTariff" class="cp-chip cp-chip--info">Системный</span>
						</div>
						<p class="cp-detail-meta">Код: <code class="cp-code">{{ currentTariff.code }}</code></p>
					</div>
					<span class="cp-chip" :class="currentTariff.is_active ? 'cp-chip--active' : 'cp-chip--inactive'">
						{{ currentTariff.is_active ? 'Активен' : 'Неактивен' }}
					</span>
				</div>

				<div v-if="loadError" class="cp-state cp-state--error" role="alert" style="min-height: auto; margin-bottom: 14px;">
					{{ loadError }}
				</div>

				<div class="cp-info-grid">
					<div class="cp-info-item">
						<span class="cp-info-label">Цена</span>
						<span class="cp-info-value cp-price">
							{{ Number(currentTariff.price_rub) === 0 ? 'Бесплатно' : `${Number(currentTariff.price_rub).toLocaleString('ru-RU')} ₽/мес` }}
						</span>
					</div>
					<div class="cp-info-item">
						<span class="cp-info-label">Создан</span>
						<span class="cp-info-value">{{ currentTariff.created_at ? new Date(currentTariff.created_at).toLocaleDateString('ru-RU') : '—' }}</span>
					</div>
					<div class="cp-info-item">
						<span class="cp-info-label">Обновлён</span>
						<span class="cp-info-value">{{ currentTariff.updated_at ? new Date(currentTariff.updated_at).toLocaleDateString('ru-RU') : '—' }}</span>
					</div>
				</div>

				<div class="cp-description-box">{{ currentTariff.description || 'Описание отсутствует.' }}</div>

				<div class="cp-section cp-actions cp-actions--end">
					<BaseButton variant="primary" text="Редактировать тариф" @click="showEditModal = true" />
				</div>
			</article>

			<section class="cp-card cp-section-card">
				<div class="cp-section-header">
					<div>
						<p class="cp-eyebrow">Ограничения</p>
						<h3 class="cp-section-title">Лимиты тарифа</h3>
						<p class="cp-muted">Ограничения функций и объёмов для выбранного плана.</p>
					</div>
					<BaseButton variant="primary" size="small" text="Добавить лимит" @click="showAddLimitModal = true" />
				</div>

				<div v-if="limits.length === 0" class="cp-state">У этого тарифа пока нет лимитов.</div>

				<div v-else class="cp-list">
					<div v-for="limit in limits" :key="limit.limit_type" class="cp-list-row">
						<div class="cp-list-row__main">
							<div class="cp-chip-row">
								<strong class="cp-list-row__title">{{ getLimitTypeLabel(limit.limit_type) }}</strong>
								<code class="cp-code">{{ limit.limit_type }}</code>
								<span v-if="requiredLimitTypes.has(limit.limit_type)" class="cp-chip cp-chip--info">Обязательный</span>
							</div>
							<p class="cp-list-row__meta">Значение: <strong>{{ limit.limit_value }}</strong></p>
						</div>
						<div class="cp-actions">
							<button class="cp-icon-button" title="Изменить" aria-label="Изменить лимит" @click="openEditLimitModal(limit)">
								<svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
								</svg>
							</button>
							<button
								class="cp-icon-button cp-icon-button--danger"
								:class="{ 'cp-icon-button--disabled': isProtectedLimit(limit) }"
								:title="isProtectedLimit(limit) ? 'Обязательный runtime-лимит активного тарифа нельзя удалить' : 'Удалить'"
								:aria-label="isProtectedLimit(limit) ? 'Удаление лимита недоступно' : 'Удалить лимит'"
								:disabled="isProtectedLimit(limit)"
								@click="askDeleteLimit(limit)"
							>
								<svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M9 7h6" />
								</svg>
							</button>
						</div>
					</div>
				</div>
			</section>
		</template>

		<EditTariffModal
			:is-open="showEditModal"
			:current-tariff="currentTariff"
			@close="showEditModal = false"
			@updated="loadTariff"
		/>
		<CreateLimit
			:is-open="showAddLimitModal"
			:tariff-id="currentTariff?.id"
			@close="showAddLimitModal = false"
			@limitCreated="loadTariff"
		/>
		<EditLimit
			:is-open="showEditLimitModal"
			:limit="currentLimit"
			@close="showEditLimitModal = false"
			@updated="loadTariff"
		/>

		<Modal v-if="deleteConfirm.isOpen" :is-open="true" @close="deleteConfirm.isOpen = false">
			<template #header>
				<h3 class="cp-modal-title">Удалить лимит</h3>
			</template>
			<template #body>
				<p class="cp-modal-copy">Удалить лимит «{{ deleteConfirm.label }}»? Это действие нельзя отменить.</p>
			</template>
			<template #footer>
				<div class="cp-actions cp-actions--end">
					<BaseButton variant="outline" text="Отмена" @click="deleteConfirm.isOpen = false" />
					<BaseButton variant="danger" text="Удалить" :loading="deleteLoading" @click="deleteLimitConfirmed" />
				</div>
			</template>
		</Modal>
	</section>
</template>
