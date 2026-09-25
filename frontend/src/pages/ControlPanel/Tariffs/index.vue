<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import CP_Tariffs from '@/API/ControlPanel/CP_Tariffs'
import BaseButton from '@/components/UI/Buttons/BaseButton.vue'
import CreateTariffModal from '@/components/TariffModals/create.vue'
import Modal from '@/components/UI/Modal.vue'

const router = useRouter()

const tariffsList = ref([])
const isLoading = ref(false)
const loadError = ref('')
const actionError = ref('')
const actionLoading = ref('')
const showCreateModal = ref(false)
const actionTariff = ref(null)
const statusConfirm = ref({
	isOpen: false,
	tariff: null,
	newStatus: false,
})
const deleteConfirm = ref({
	isOpen: false,
	tariff: null,
	code: '',
	error: '',
})

const isSystemTariff = (tariff) =>
	String(tariff?.code || '').toLowerCase() === 'demo'

const priceLabel = (tariff) =>
	Number(tariff?.price_rub) === 0
		? 'Бесплатно'
		: `${Number(tariff?.price_rub || 0).toLocaleString('ru-RU')} ₽/мес`

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
		loadError.value =
			error.response?.data?.error?.message ||
			'Не удалось загрузить тарифные планы.'
	} finally {
		isLoading.value = false
	}
}

function openActions(tariff) {
	actionTariff.value = tariff
	actionError.value = ''
}

function closeActions() {
	if (actionLoading.value) return
	actionTariff.value = null
}

function editTariff(tariff) {
	actionTariff.value = null
	router.push({
		name: 'control-panel.edit-tariff',
		params: { id: tariff.id },
	})
}

function askStatusChange(tariff) {
	if (actionLoading.value || isSystemTariff(tariff)) return
	actionTariff.value = null
	statusConfirm.value = {
		isOpen: true,
		tariff,
		newStatus: !tariff.is_active,
	}
}

function closeStatusConfirm() {
	if (actionLoading.value) return
	statusConfirm.value = {
		isOpen: false,
		tariff: null,
		newStatus: false,
	}
}

async function applyStatusChange() {
	const tariff = statusConfirm.value.tariff
	if (!tariff || actionLoading.value) return

	actionLoading.value = 'status'
	actionError.value = ''
	try {
		const response = await CP_Tariffs.updateTariffStatus(
			tariff.id,
			statusConfirm.value.newStatus,
		)
		if (response.data?.status !== 'success') {
			throw new Error(
				response.data?.error?.message ||
				response.data?.message ||
				'Не удалось изменить статус тарифа'
			)
		}
		closeStatusConfirm()
		await loadTariffs()
	} catch (error) {
		console.error('Ошибка изменения статуса тарифа:', error)
		actionError.value =
			error.response?.data?.error?.message ||
			error.message ||
			'Не удалось изменить статус тарифа.'
		statusConfirm.value = {
			isOpen: false,
			tariff: null,
			newStatus: false,
		}
	} finally {
		actionLoading.value = ''
	}
}

function openDelete(tariff) {
	if (
		actionLoading.value ||
		isSystemTariff(tariff) ||
		tariff.is_active
	) return

	actionTariff.value = null
	deleteConfirm.value = {
		isOpen: true,
		tariff,
		code: '',
		error: '',
	}
}

function closeDelete() {
	if (actionLoading.value === 'delete') return
	deleteConfirm.value = {
		isOpen: false,
		tariff: null,
		code: '',
		error: '',
	}
}

function tariffUsageMessage(error) {
	const usage = error?.response?.data?.error?.usage
	if (!usage) return ''

	const subscriptions = Number(usage.subscriptions || 0)
	const payments = Number(usage.payments || 0)
	return `Связанные записи: подписки — ${subscriptions}, платежи — ${payments}.`
}

async function deleteTariffConfirmed() {
	const tariff = deleteConfirm.value.tariff
	if (!tariff || tariff.is_active || isSystemTariff(tariff) || actionLoading.value) {
		return
	}

	const expected = String(tariff.code || '').trim().toLowerCase()
	const actual = String(deleteConfirm.value.code || '').trim().toLowerCase()
	if (!actual || actual !== expected) {
		deleteConfirm.value.error =
			'Введите код тарифа точно так, как он указан выше.'
		return
	}

	actionLoading.value = 'delete'
	deleteConfirm.value.error = ''
	try {
		const response = await CP_Tariffs.deleteTariff(tariff.id)
		if (response.data?.status !== 'success' || response.data?.deleting !== true) {
			throw new Error(
				response.data?.error?.message ||
				'Тариф не удалён'
			)
		}
		deleteConfirm.value = {
			isOpen: false,
			tariff: null,
			code: '',
			error: '',
		}
		await loadTariffs()
	} catch (error) {
		console.error('Ошибка удаления тарифа:', error)
		const baseMessage =
			error.response?.data?.error?.message ||
			error.message ||
			'Не удалось удалить тариф.'
		const usage = tariffUsageMessage(error)
		deleteConfirm.value.error = usage
			? `${baseMessage} ${usage}`
			: baseMessage
	} finally {
		actionLoading.value = ''
	}
}

async function handleCreated() {
	showCreateModal.value = false
	await loadTariffs()
}
</script>

<template>
	<section class="cp-page">
		<header class="cp-page-header">
			<div>
				<p class="cp-eyebrow">Монетизация</p>
				<h2 class="cp-detail-title">Тарифные планы</h2>
				<p class="cp-subtitle">
					Активный тариф сначала деактивируется. Неактивный можно удалить только если на него не ссылаются подписки или платежи.
				</p>
			</div>
			<BaseButton
				variant="primary"
				text="Создать тариф"
				:disabled="Boolean(actionLoading)"
				@click="showCreateModal = true"
			/>
		</header>

		<div v-if="actionError" class="cp-state cp-state--error cp-state--compact" role="alert">
			{{ actionError }}
		</div>

		<div v-if="isLoading" class="cp-state" role="status">
			Загружаем тарифы…
		</div>

		<div v-else-if="loadError" class="cp-state cp-state--error" role="alert">
			<div class="cp-state__stack">
				<strong>{{ loadError }}</strong>
				<BaseButton
					variant="outline"
					size="small"
					text="Повторить"
					@click="loadTariffs"
				/>
			</div>
		</div>

		<div v-else-if="tariffsList.length === 0" class="cp-state">
			<div class="cp-state__stack">
				<strong>Тарифов пока нет.</strong>
				<span>Создайте первый тарифный план, затем настройте его лимиты и активируйте.</span>
				<BaseButton
					variant="primary"
					size="small"
					text="Создать тариф"
					@click="showCreateModal = true"
				/>
			</div>
		</div>

		<section v-else class="cp-card tariff-list">
			<div class="tariff-list__head" aria-hidden="true">
				<span>Тариф</span>
				<span>Стоимость</span>
				<span>Состояние</span>
				<span>Действия</span>
			</div>

			<article
				v-for="tariff in tariffsList"
				:key="tariff.id"
				class="tariff-row"
				:class="{
					'tariff-row--inactive': !tariff.is_active,
					'tariff-row--system': isSystemTariff(tariff),
				}"
			>
				<div class="tariff-main">
					<div class="tariff-title-row">
						<strong>{{ tariff.name }}</strong>
						<code class="cp-code">{{ tariff.code }}</code>
						<span v-if="isSystemTariff(tariff)" class="cp-chip cp-chip--info">Системный</span>
					</div>
					<p>{{ tariff.description || 'Описание не добавлено.' }}</p>
				</div>

				<div class="tariff-price">
					<strong>{{ priceLabel(tariff) }}</strong>
				</div>

				<div class="tariff-status">
					<span
						class="cp-chip"
						:class="tariff.is_active ? 'cp-chip--active' : 'cp-chip--inactive'"
					>
						{{ tariff.is_active ? 'Активен' : 'Неактивен' }}
					</span>
					<span
						class="cp-chip"
						:class="tariff.is_public ? 'cp-chip--active' : 'cp-chip--inactive'"
					>
						{{ tariff.is_public ? 'Публичный' : 'Скрытый' }}
					</span>
				</div>

				<div class="tariff-actions">
					<BaseButton
						variant="outline"
						size="small"
						text="Действия"
						:disabled="Boolean(actionLoading)"
						@click="openActions(tariff)"
					/>
				</div>
			</article>
		</section>

		<CreateTariffModal
			:is-open="showCreateModal"
			@close="showCreateModal = false"
			@created="handleCreated"
		/>

		<Modal
			v-if="actionTariff"
			:is-open="true"
			aria-label="Действия с тарифом"
			:close-on-overlay-click="!actionLoading"
			:close-on-escape="!actionLoading"
			@close="closeActions"
		>
			<template #header>
				<div>
					<h3 class="cp-modal-title">{{ actionTariff.name }}</h3>
					<p class="cp-muted">{{ actionTariff.code }}</p>
				</div>
			</template>

			<template #body>
				<div class="tariff-action-menu">
					<BaseButton
						variant="outline"
						text="Редактировать тариф"
						:disabled="Boolean(actionLoading)"
						@click="editTariff(actionTariff)"
					/>

					<BaseButton
						v-if="!isSystemTariff(actionTariff)"
						:variant="actionTariff.is_active ? 'outline' : 'success'"
						:text="actionTariff.is_active ? 'Деактивировать' : 'Активировать'"
						:disabled="Boolean(actionLoading)"
						@click="askStatusChange(actionTariff)"
					/>

					<BaseButton
						v-if="!isSystemTariff(actionTariff) && !actionTariff.is_active"
						variant="danger"
						text="Удалить…"
						:disabled="Boolean(actionLoading)"
						@click="openDelete(actionTariff)"
					/>

					<div v-if="!isSystemTariff(actionTariff) && actionTariff.is_active" class="tariff-delete-hint">
						<strong>Удаление недоступно, пока тариф активен.</strong>
						<span>Сначала деактивируйте тариф. После этого появится действие «Удалить…».</span>
					</div>

					<div v-if="isSystemTariff(actionTariff)" class="tariff-delete-hint">
						<strong>Системный тариф защищён.</strong>
						<span>Demo нельзя деактивировать или удалить.</span>
					</div>
				</div>
			</template>

			<template #footer>
				<div class="cp-modal-footer">
					<BaseButton
						variant="outline"
						text="Закрыть"
						:disabled="Boolean(actionLoading)"
						@click="closeActions"
					/>
				</div>
			</template>
		</Modal>

		<Modal
			v-if="statusConfirm.isOpen"
			:is-open="true"
			aria-label="Подтверждение изменения статуса тарифа"
			:close-on-overlay-click="!actionLoading"
			:close-on-escape="!actionLoading"
			@close="closeStatusConfirm"
		>
			<template #header>
				<h3 class="cp-modal-title">
					{{ statusConfirm.newStatus ? 'Активировать тариф' : 'Деактивировать тариф' }}
				</h3>
			</template>
			<template #body>
				<p class="cp-modal-copy">
					<template v-if="statusConfirm.newStatus">
						Активировать тариф «{{ statusConfirm.tariff?.name }}»?
					</template>
					<template v-else>
						Деактивировать тариф «{{ statusConfirm.tariff?.name }}»?
						Он станет скрытым для новых подключений, но исторические подписки и платежи сохранятся.
					</template>
				</p>
			</template>
			<template #footer>
				<div class="cp-modal-footer">
					<BaseButton variant="outline" text="Отмена" :disabled="Boolean(actionLoading)" @click="closeStatusConfirm" />
					<BaseButton
						:variant="statusConfirm.newStatus ? 'success' : 'danger'"
						:text="statusConfirm.newStatus ? 'Активировать' : 'Деактивировать'"
						loading-text="Сохраняем…"
						:loading="actionLoading === 'status'"
						@click="applyStatusChange"
					/>
				</div>
			</template>
		</Modal>

		<Modal
			v-if="deleteConfirm.isOpen"
			:is-open="true"
			aria-label="Необратимое удаление тарифа"
			:close-on-overlay-click="actionLoading !== 'delete'"
			:close-on-escape="actionLoading !== 'delete'"
			@close="closeDelete"
		>
			<template #header>
				<h3 class="cp-modal-title">Удалить тариф навсегда</h3>
			</template>

			<template #body>
				<div class="delete-tariff">
					<p>
						Удаляется только неактивный тариф без связанных подписок и платежей.
						Если тариф уже использовался, система сохранит его неактивным для истории.
					</p>
					<p>
						Для подтверждения введите код
						<strong>{{ deleteConfirm.tariff?.code }}</strong>.
					</p>
					<label class="cp-field-label">
						<span>Код тарифа</span>
						<input
							v-model="deleteConfirm.code"
							type="text"
							autocomplete="off"
							:placeholder="deleteConfirm.tariff?.code || ''"
							:disabled="actionLoading === 'delete'"
						/>
					</label>
					<p v-if="deleteConfirm.error" class="delete-error" role="alert">
						{{ deleteConfirm.error }}
					</p>
				</div>
			</template>

			<template #footer>
				<div class="cp-modal-footer">
					<BaseButton
						variant="outline"
						text="Отмена"
						:disabled="actionLoading === 'delete'"
						@click="closeDelete"
					/>
					<BaseButton
						variant="danger"
						text="Удалить навсегда"
						loading-text="Удаляем…"
						:loading="actionLoading === 'delete'"
						@click="deleteTariffConfirmed"
					/>
				</div>
			</template>
		</Modal>
	</section>
</template>

<style scoped>
.cp-state--compact {
	min-height: auto;
	margin-bottom: 12px;
}

.tariff-list {
	padding: 0;
	overflow: hidden;
}

.tariff-list__head,
.tariff-row {
	display: grid;
	grid-template-columns: minmax(260px, 2fr) minmax(120px, .7fr) minmax(180px, 1fr) 110px;
	gap: 16px;
	align-items: center;
}

.tariff-list__head {
	padding: 10px 16px;
	border-bottom: 1px solid var(--border-color);
	background: var(--light-bg);
	color: var(--text-muted);
	font-size: 10px;
	font-weight: 800;
	letter-spacing: .04em;
	text-transform: uppercase;
}

.tariff-row {
	min-height: 92px;
	padding: 14px 16px;
	border-bottom: 1px solid var(--border-color);
}

.tariff-row:last-child {
	border-bottom: 0;
}

.tariff-row--inactive {
	background: color-mix(in srgb, var(--light-bg) 45%, var(--card-bg));
}

.tariff-row--system {
	box-shadow: inset 3px 0 0 color-mix(in srgb, var(--secondary-color) 55%, transparent);
}

.tariff-main {
	min-width: 0;
}

.tariff-title-row {
	display: flex;
	align-items: center;
	gap: 7px;
	flex-wrap: wrap;
}

.tariff-title-row strong {
	font-size: 14px;
}

.tariff-main p {
	margin: 5px 0 0;
	color: var(--text-muted);
	font-size: 11px;
	line-height: 1.45;
	overflow-wrap: anywhere;
}

.tariff-price strong {
	font-size: 13px;
}

.tariff-status {
	display: flex;
	gap: 6px;
	flex-wrap: wrap;
}

.tariff-actions {
	display: flex;
	justify-content: flex-end;
}

.tariff-action-menu {
	display: grid;
	gap: 9px;
}

.tariff-action-menu :deep(.base-button) {
	width: 100%;
}

.tariff-delete-hint {
	padding: 10px 12px;
	display: grid;
	gap: 4px;
	border-radius: 9px;
	background: var(--light-bg);
}

.tariff-delete-hint strong {
	font-size: 11px;
}

.tariff-delete-hint span,
.delete-tariff p {
	color: var(--text-muted);
	font-size: 11px;
	line-height: 1.5;
}

.delete-tariff {
	display: grid;
	gap: 12px;
}

.delete-tariff p {
	margin: 0;
}

.delete-error {
	margin: 0;
	color: var(--danger-color);
	font-size: 12px;
	line-height: 1.5;
}

@media (max-width: 820px) {
	.tariff-list__head {
		display: none;
	}

	.tariff-row {
		grid-template-columns: minmax(0, 1fr) auto;
		gap: 10px 14px;
	}

	.tariff-main {
		grid-column: 1 / -1;
	}

	.tariff-price,
	.tariff-status {
		align-self: center;
	}

	.tariff-actions {
		grid-column: 2;
		grid-row: 2 / span 2;
		align-self: center;
	}
}

@media (max-width: 520px) {
	.tariff-row {
		grid-template-columns: 1fr;
	}

	.tariff-main,
	.tariff-actions {
		grid-column: 1;
	}

	.tariff-actions {
		grid-row: auto;
		justify-content: stretch;
	}

	.tariff-actions :deep(.base-button) {
		width: 100%;
	}
}
</style>
