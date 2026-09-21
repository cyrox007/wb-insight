<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import BaseButton from '@/components/UI/Buttons/BaseButton.vue'
import Modal from '@/components/UI/Modal.vue'
import CP_Payments from '@/API/ControlPanel/CP_Payments'

const activeSection = ref('providers')
const providers = ref([])
const payments = ref([])
const canManage = ref(false)
const isLoading = ref(false)
const loadError = ref('')
const saveError = ref('')
const savingKey = ref('')
const editingKey = ref('')
const paymentDetail = ref(null)
const detailLoading = ref(false)

const filters = reactive({ provider: '', mode: '', status: '', email: '' })
const form = reactive({
	enabled: false,
	is_default: false,
	api_base_url: '',
	return_url: '',
	fail_url: '',
	currency_code: '643',
	timeout_seconds: '10',
	username: '',
	password: '',
	clear_secrets: false,
})

const providerKey = (provider) => `${provider.provider}:${provider.mode}`
const modeLabel = (mode) => mode === 'live' ? 'Боевой' : 'Тестовый'
const statusLabel = (value) => ({ pending: 'Ожидает', succeeded: 'Оплачен', failed: 'Ошибка', cancelled: 'Отменён' }[value] || value)
const providerLabel = (value) => ({ sber: 'Сбер', fake: 'Тестовая оплата', yookassa: 'ЮKassa' }[value] || value)

const configuredCount = computed(() => providers.value.filter((item) => item.enabled).length)
const editingProvider = computed(
	() => providers.value.find((provider) => providerKey(provider) === editingKey.value) || null
)

async function loadProviders() {
	isLoading.value = true
	loadError.value = ''
	try {
		const { data } = await CP_Payments.getProviders()
		if (data?.status !== 'success' || !Array.isArray(data?.providers)) throw new Error('Некорректный ответ API')
		providers.value = data.providers
		canManage.value = Boolean(data.can_manage)
	} catch (error) {
		console.error('Ошибка загрузки платёжных систем:', error)
		loadError.value = 'Не удалось загрузить настройки платёжных систем.'
	} finally {
		isLoading.value = false
	}
}

async function loadJournal() {
	isLoading.value = true
	loadError.value = ''
	try {
		const params = Object.fromEntries(Object.entries(filters).filter(([, value]) => value))
		const { data } = await CP_Payments.getJournal(params)
		if (data?.status !== 'success' || !Array.isArray(data?.payments)) throw new Error('Некорректный ответ API')
		payments.value = data.payments
	} catch (error) {
		console.error('Ошибка загрузки журнала оплат:', error)
		loadError.value = 'Не удалось загрузить журнал оплат.'
	} finally {
		isLoading.value = false
	}
}

function switchSection(section) {
	activeSection.value = section
	loadError.value = ''
	paymentDetail.value = null
	if (section === 'providers') loadProviders()
	if (section === 'journal') loadJournal()
}

function startEdit(provider) {
	editingKey.value = providerKey(provider)
	saveError.value = ''
	Object.assign(form, {
		enabled: Boolean(provider.enabled),
		is_default: Boolean(provider.is_default),
		api_base_url: provider.api_base_url || '',
		return_url: provider.return_url || '',
		fail_url: provider.fail_url || '',
		currency_code: provider.currency_code || '643',
		timeout_seconds: String(provider.timeout_seconds || 10),
		username: '',
		password: '',
		clear_secrets: false,
	})
}

function cancelEdit() {
	editingKey.value = ''
	saveError.value = ''
}

async function saveProvider(provider) {
	const key = providerKey(provider)
	savingKey.value = key
	saveError.value = ''
	try {
		const payload = {
			enabled: form.enabled,
			is_default: form.is_default,
			api_base_url: form.api_base_url,
			return_url: form.return_url,
			fail_url: form.fail_url,
			currency_code: form.currency_code,
			timeout_seconds: Number(form.timeout_seconds || 10),
			clear_secrets: form.clear_secrets,
		}
		if (form.username) payload.username = form.username
		if (form.password) payload.password = form.password
		const { data } = await CP_Payments.updateProvider(provider.provider, provider.mode, payload)
		if (data?.status !== 'success') throw new Error(data?.error?.message || 'Не удалось сохранить настройки')
		providers.value = data.providers || providers.value
		editingKey.value = ''
	} catch (error) {
		console.error('Ошибка сохранения платёжной системы:', error)
		saveError.value = error.response?.data?.error?.message || error.message || 'Не удалось сохранить настройки.'
	} finally {
		savingKey.value = ''
	}
}

async function openPayment(payment) {
	detailLoading.value = true
	paymentDetail.value = null
	try {
		const { data } = await CP_Payments.getPayment(payment.id)
		if (data?.status !== 'success' || !data?.payment) throw new Error('Некорректный ответ API')
		paymentDetail.value = data.payment
	} catch (error) {
		console.error('Ошибка загрузки платежа:', error)
		loadError.value = 'Не удалось загрузить карточку платежа.'
	} finally {
		detailLoading.value = false
	}
}

onMounted(loadProviders)
</script>

<template>
	<section class="cp-page">
		<header class="cp-page-header">
			<div>
				<p class="cp-eyebrow">Монетизация</p>
				<h2 class="cp-detail-title">Платежи</h2>
				<p class="cp-subtitle">Платёжные системы, test/live режимы и журнал оплат тарифов.</p>
			</div>
		</header>

		<div class="cp-segmented" role="tablist" aria-label="Разделы платежей">
			<button
				type="button"
				role="tab"
				class="cp-segmented__button"
				:class="{ 'is-active': activeSection === 'providers' }"
				:aria-selected="activeSection === 'providers'"
				@click="switchSection('providers')"
			>
				Платёжные системы
			</button>
			<button
				type="button"
				role="tab"
				class="cp-segmented__button"
				:class="{ 'is-active': activeSection === 'journal' }"
				:aria-selected="activeSection === 'journal'"
				@click="switchSection('journal')"
			>
				Журнал оплат
			</button>
		</div>

		<div v-if="isLoading" class="cp-state" role="status">Загружаем данные…</div>
		<div v-else-if="loadError" class="cp-state cp-state--error" role="alert">
			<div class="cp-state__stack">
				<strong>{{ loadError }}</strong>
				<BaseButton variant="outline" size="small" text="Повторить" @click="activeSection === 'providers' ? loadProviders() : loadJournal()" />
			</div>
		</div>

		<template v-else-if="activeSection === 'providers'">
			<div class="payments-summary">
				<span class="cp-chip cp-chip--accent">{{ configuredCount }} включено</span>
				<span class="cp-muted">Изменение конфигурации доступно только суперадминистратору. Секреты после сохранения не возвращаются в браузер.</span>
			</div>

			<div class="provider-grid">
				<article v-for="provider in providers" :key="providerKey(provider)" class="cp-card provider-card">
					<div class="provider-card__head">
						<div>
							<div class="provider-title-row">
								<h3 class="provider-card__title">{{ provider.name }}</h3>
								<span class="cp-chip" :class="provider.mode === 'live' ? 'cp-chip--active' : 'cp-chip--warning'">{{ modeLabel(provider.mode) }}</span>
							</div>
							<p class="cp-card-note">{{ provider.description }}</p>
						</div>
						<span class="cp-chip" :class="provider.ready ? 'cp-chip--active' : 'cp-chip--inactive'">{{ provider.ready ? 'Готов' : 'Не готов' }}</span>
					</div>

					<div class="provider-meta">
						<div><span>Статус</span><strong>{{ provider.enabled ? 'Включён' : 'Выключен' }}</strong></div>
						<div><span>По умолчанию</span><strong>{{ provider.is_default ? 'Да' : 'Нет' }}</strong></div>
						<div><span>Источник</span><strong>{{ provider.source === 'database' ? 'Панель управления' : provider.source === 'environment' ? 'ENV' : 'Не настроен' }}</strong></div>
						<div><span>Credentials</span><strong>{{ provider.credentials_configured ? (provider.credential_hint || 'Настроены') : 'Не настроены' }}</strong></div>
					</div>

					<div v-if="!provider.adapter_available" class="provider-note">Адаптер ещё не подключён. Настройки зарезервированы для следующего этапа интеграции.</div>

					<div class="cp-actions">
						<BaseButton variant="outline" size="small" text="Настроить" :disabled="!canManage" @click="startEdit(provider)" />
					</div>
				</article>
			</div>

			<Modal
				:is-open="Boolean(editingProvider)"
				size="large"
				:aria-label="editingProvider ? `Настройка ${editingProvider.name}` : 'Настройка платёжной системы'"
				@close="cancelEdit"
			>
				<template #header>
					<div class="provider-modal__header">
						<div>
							<p class="cp-eyebrow">Платёжная система</p>
							<h3 class="cp-modal-title">{{ editingProvider?.name || 'Настройка' }}</h3>
							<p v-if="editingProvider" class="cp-modal-copy">{{ modeLabel(editingProvider.mode) }} режим · секреты после сохранения не возвращаются в браузер.</p>
						</div>
					</div>
				</template>

				<template #body>
					<form
						v-if="editingProvider"
						id="provider-config-form"
						class="provider-form provider-form--modal"
						@submit.prevent="saveProvider(editingProvider)"
					>
						<div v-if="saveError" class="cp-state cp-state--error" role="alert">{{ saveError }}</div>

						<div class="provider-form__checks">
							<label><input v-model="form.enabled" type="checkbox"> Включён</label>
							<label><input v-model="form.is_default" type="checkbox"> Провайдер по умолчанию</label>
						</div>

						<label class="provider-field">API URL<input v-model.trim="form.api_base_url" type="url" placeholder="https://…"></label>
						<label class="provider-field">Return URL<input v-model.trim="form.return_url" type="url" placeholder="https://…"></label>
						<label class="provider-field">Fail URL<input v-model.trim="form.fail_url" type="url" placeholder="https://…"></label>

						<div class="provider-form__row">
							<label class="provider-field">Код валюты<input v-model.trim="form.currency_code" type="text"></label>
							<label class="provider-field">Timeout, сек.<input v-model="form.timeout_seconds" type="number" min="1" max="120"></label>
						</div>

						<div class="provider-form__row">
							<label class="provider-field">Логин<input v-model.trim="form.username" type="text" autocomplete="off" placeholder="Пусто = оставить текущий"></label>
							<label class="provider-field">Пароль<input v-model="form.password" type="password" autocomplete="new-password" placeholder="Пусто = оставить текущий"></label>
						</div>

						<label class="provider-clear"><input v-model="form.clear_secrets" type="checkbox"> Очистить сохранённые credentials</label>
					</form>
				</template>

				<template #footer>
					<div class="cp-modal-footer">
						<BaseButton variant="outline" text="Отмена" @click="cancelEdit" />
						<BaseButton
							type="submit"
							form="provider-config-form"
							variant="primary"
							text="Сохранить"
							:loading="editingProvider && savingKey === providerKey(editingProvider)"
							:disabled="!editingProvider"
						/>
					</div>
				</template>
			</Modal>
		</template>

		<template v-else>
			<div class="cp-card cp-filter-surface">
				<label class="cp-field-label">
					<span>Email пользователя</span>
					<input v-model.trim="filters.email" type="search" placeholder="seller@example.com">
				</label>
				<label class="cp-field-label">
					<span>Провайдер</span>
					<select v-model="filters.provider"><option value="">Все провайдеры</option><option value="sber">Сбер</option><option value="fake">Тестовая оплата</option><option value="yookassa">ЮKassa</option></select>
				</label>
				<label class="cp-field-label">
					<span>Режим</span>
					<select v-model="filters.mode"><option value="">Все режимы</option><option value="live">Боевой</option><option value="test">Тестовый</option></select>
				</label>
				<label class="cp-field-label">
					<span>Статус</span>
					<select v-model="filters.status"><option value="">Все статусы</option><option value="pending">Ожидает</option><option value="succeeded">Оплачен</option><option value="failed">Ошибка</option><option value="cancelled">Отменён</option></select>
				</label>
				<div class="cp-filter-surface__actions">
					<BaseButton variant="primary" size="small" text="Применить" @click="loadJournal" />
				</div>
			</div>

			<div v-if="payments.length === 0" class="cp-state">Платежей пока нет.</div>
			<div v-else class="cp-table-wrap">
				<div class="cp-table-scroll">
					<table class="cp-table">
						<thead><tr><th>Дата</th><th>Пользователь</th><th>Тариф</th><th>Сумма</th><th>Провайдер</th><th>Режим</th><th>Статус</th><th>ID провайдера</th><th></th></tr></thead>
						<tbody>
							<tr v-for="payment in payments" :key="payment.id">
								<td>{{ payment.created_at ? new Date(payment.created_at).toLocaleString('ru-RU') : '—' }}</td>
								<td>{{ payment.user_email || '—' }}</td>
								<td>{{ payment.tariff_name || '—' }}</td>
								<td>{{ Number(payment.amount).toLocaleString('ru-RU') }} {{ payment.currency }}</td>
								<td>{{ providerLabel(payment.provider) }}</td>
								<td><span class="cp-chip" :class="payment.mode === 'live' ? 'cp-chip--active' : 'cp-chip--warning'">{{ modeLabel(payment.mode) }}</span></td>
								<td>{{ statusLabel(payment.status) }}</td>
								<td><code class="cp-code">{{ payment.external_payment_id || '—' }}</code></td>
								<td><BaseButton variant="ghost" size="small" text="Детали" @click="openPayment(payment)" /></td>
							</tr>
						</tbody>
					</table>
				</div>
			</div>

			<div v-if="detailLoading" class="cp-state">Загружаем карточку платежа…</div>
			<article v-else-if="paymentDetail" class="cp-card payment-detail">
				<div class="payment-detail__head"><div><p class="cp-eyebrow">Платёж</p><h3>{{ paymentDetail.id }}</h3></div><BaseButton variant="ghost" size="small" text="Закрыть" @click="paymentDetail = null" /></div>
				<div class="provider-meta"><div><span>Пользователь</span><strong>{{ paymentDetail.user_email }}</strong></div><div><span>Тариф</span><strong>{{ paymentDetail.tariff_name }}</strong></div><div><span>Статус</span><strong>{{ statusLabel(paymentDetail.status) }}</strong></div><div><span>Провайдер</span><strong>{{ providerLabel(paymentDetail.provider) }} · {{ modeLabel(paymentDetail.mode) }}</strong></div></div>
				<h4>События</h4>
				<div v-if="!paymentDetail.events?.length" class="cp-muted">Событий пока нет.</div>
				<div v-for="event in paymentDetail.events" :key="event.id" class="payment-event"><div><strong>{{ event.event_type }}</strong><span>{{ event.created_at ? new Date(event.created_at).toLocaleString('ru-RU') : '' }}</span></div><code>{{ event.provider_status || '—' }}</code></div>
			</article>
		</template>
	</section>
</template>

<style scoped>
.payments-summary { display:flex; align-items:center; gap:12px; }
.provider-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(340px,1fr)); gap:14px; align-items:start; }
.provider-card { display:flex; flex-direction:column; gap:16px; align-self:start; padding:18px; transition:border-color 220ms ease,box-shadow 220ms ease; }
.provider-card__head,.provider-title-row,.payment-detail__head { display:flex; align-items:flex-start; justify-content:space-between; gap:12px; }
.provider-title-row { justify-content:flex-start; align-items:center; }
.provider-card__title { margin:0; }
.provider-meta { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; }
.provider-meta > div { display:flex; flex-direction:column; gap:4px; padding:10px; border:1px solid var(--border-color); border-radius:8px; }
.provider-meta span { color:var(--text-muted); font-size:12px; }
.provider-note { padding:10px 12px; border:1px dashed var(--border-color); border-radius:8px; color:var(--text-muted,#91a4bf); }
.provider-form { display:grid; gap:12px; }
.provider-form--modal { padding:2px 0 0; }
.provider-modal__header { display:flex; justify-content:space-between; gap:14px; }
.provider-modal__header .cp-modal-copy { margin-top:5px; }
.provider-form__checks,.provider-form__row { display:flex; gap:14px; }
.provider-form__checks { margin-bottom:12px; flex-wrap:wrap; }
.provider-field { display:flex; flex-direction:column; gap:6px; flex:1; margin-bottom:10px; font-size:13px; }
.provider-field input,.filter-input { min-height:42px; }
.provider-clear { display:block; margin:8px 0 14px; color:var(--text-muted,#91a4bf); font-size:13px; }
.payment-detail { padding:18px; }
.payment-detail h3 { margin:2px 0 0; font-size:16px; word-break:break-all; }
.payment-event { display:flex; justify-content:space-between; gap:12px; padding:10px 0; border-top:1px solid var(--border-color); }
.payment-event > div { display:flex; flex-direction:column; gap:2px; }
.payment-event span { font-size:12px; color:var(--text-muted,#91a4bf); }
@media (max-width:760px) { .provider-grid { grid-template-columns:1fr; }.provider-form__row,.payments-summary { flex-direction:column; align-items:stretch; }.provider-meta { grid-template-columns:1fr; }.provider-card { padding:16px; } }
</style>
