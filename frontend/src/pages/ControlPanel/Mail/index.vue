<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import CP_Mail from '@/API/ControlPanel/CP_Mail'
import BaseButton from '@/components/UI/Buttons/BaseButton.vue'
import Modal from '@/components/UI/Modal.vue'
import MailComposer from '@/components/ControlPanel/MailComposer.vue'

const activeTab = ref('campaigns')
const meta = ref({ roles: [], tariffs: [], subscription_statuses: [], can_manage: false, gateway: null })
const campaigns = ref([])
const campaignTotal = ref(0)
const campaignOffset = ref(0)
const campaignLimit = 20
const campaignStatus = ref('')
const selected = ref(null)
const messages = ref([])
const messageTotal = ref(0)
const messageOffset = ref(0)
const messageLimit = 50
const messageStatus = ref('')
const loading = ref(false)
const error = ref('')
const actionMessage = ref('')
const actionIsError = ref(false)
const editing = ref(false)
const editingId = ref('')
const audiencePreview = ref(null)
const testEmail = ref('')
const scheduleAt = ref('')
const confirmAction = ref(null)
const gatewayBusy = ref(false)
const gatewayTestEmail = ref('')

const form = reactive({
	name: '',
	subject: '',
	body_html: '',
	verified_only: true,
	active_mode: 'active',
	roles: [],
	tariff_codes: [],
	subscription_statuses: [],
})

const gatewayForm = reactive({
	provider: 'smtp',
	enabled: false,
	host: '',
	port: 587,
	api_base_url: 'https://api.rusender.ru',
	key_id: '',
	api_token: '',
	from_email: '',
	from_name: 'WB Insight',
	reply_to_email: '',
	starttls: true,
	timeout_seconds: 10,
	username: '',
	password: '',
	clear_credentials: false,
})

const roleLabels = {
	super_admin: 'Суперадмин',
	admin: 'Администратор',
	manager: 'Менеджер',
	support: 'Поддержка',
	analyst: 'Аналитик',
	user: 'Пользователь',
}
const subscriptionLabels = {
	demo: 'DEMO',
	active: 'Активная',
	expired: 'Истекла',
	cancelled: 'Отменена',
}

const canManage = computed(() => Boolean(meta.value.can_manage))
const campaignPage = computed(() => Math.floor(campaignOffset.value / campaignLimit) + 1)
const campaignPages = computed(() => Math.max(1, Math.ceil(campaignTotal.value / campaignLimit)))
const messagePage = computed(() => Math.floor(messageOffset.value / messageLimit) + 1)
const messagePages = computed(() => Math.max(1, Math.ceil(messageTotal.value / messageLimit)))
const minScheduleAt = computed(() => {
	const date = new Date(Date.now() + 60_000)
	return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16)
})
const confirmTitle = computed(() => confirmAction.value === 'cancel' ? 'Остановить рассылку?' : 'Запустить рассылку?')
const confirmText = computed(() => confirmAction.value === 'cancel'
	? 'Все ещё неотправленные письма этой кампании будут отменены. Уже отправленные письма отозвать нельзя.'
	: 'Кампания будет зафиксирована на текущую аудиторию и поставлена в очередь доставки.')
const selectedPreviewDocument = computed(() => {
	const body = selected.value?.body_html || `<p>${escapeHtml(selected.value?.body || '')}</p>`
	return mailPreviewDocument(body)
})

const starterTemplates = [
	{
		code: 'promo',
		name: 'Промо',
		subject: 'Специальное предложение для продавцов Wildberries',
		html: '<h2>Есть идея, как улучшить ваш результат на Wildberries</h2><p>Мы подготовили новые возможности WB Insight, которые помогут быстрее увидеть точки роста и контролировать прибыль.</p><p><strong>Что можно сделать прямо сейчас:</strong></p><ul><li>проверить прибыль и выплаты;</li><li>найти товары с риском по остаткам;</li><li>оценить эффективность рекламы.</li></ul><p><a href="https://wb.jsinteractive.ru" data-mail-button="1">Открыть WB Insight</a></p>',
	},
	{
		code: 'update',
		name: 'Обновление продукта',
		subject: 'Что нового в WB Insight',
		html: '<h2>WB Insight стал удобнее</h2><p>Мы обновили сервис и добавили новые инструменты для ежедневной работы с кабинетом Wildberries.</p><h3>В этом обновлении</h3><ul><li>улучшенная аналитика;</li><li>новые состояния интерфейса;</li><li>более понятное управление данными.</li></ul><p><a href="https://wb.jsinteractive.ru" data-mail-button="1">Посмотреть обновление</a></p>',
	},
	{
		code: 'service',
		name: 'Сервисное сообщение',
		subject: 'Важная информация от WB Insight',
		html: '<h2>Важная информация</h2><p>Здравствуйте!</p><p>Сообщаем об изменении, которое может повлиять на работу вашего аккаунта WB Insight.</p><blockquote>Добавьте сюда главное сообщение, сроки и необходимые действия.</blockquote><p>Если у вас возникнут вопросы, ответьте на это письмо или обратитесь в поддержку.</p>',
	},
]

function escapeHtml(value) {
	return String(value || '')
		.replaceAll('&', '&amp;')
		.replaceAll('<', '&lt;')
		.replaceAll('>', '&gt;')
		.replaceAll('"', '&quot;')
}

function mailPreviewDocument(fragment) {
	return `<!doctype html><html><body style="margin:0;padding:24px;background:#f5f6fb;font-family:Arial,sans-serif;color:#182033"><div style="max-width:640px;margin:auto;background:#fff;padding:32px;border-radius:16px;box-sizing:border-box">${fragment || '<p style="color:#94a3b8">Пустое письмо</p>'}</div></body></html>`
}

function segmentPayload() {
	const segment = {
		verified_only: form.verified_only,
		roles: [...form.roles],
		tariff_codes: [...form.tariff_codes],
		subscription_statuses: [...form.subscription_statuses],
	}
	if (form.active_mode === 'active') segment.active = true
	if (form.active_mode === 'inactive') segment.active = false
	return segment
}

function setMessage(message, isError = false) {
	actionMessage.value = message
	actionIsError.value = isError
}

function resetEditor() {
	editing.value = false
	editingId.value = ''
	audiencePreview.value = null
	Object.assign(form, {
		name: '',
		subject: '',
		body_html: '',
		verified_only: true,
		active_mode: 'active',
		roles: [],
		tariff_codes: [],
		subscription_statuses: [],
	})
}

function newCampaign() {
	resetEditor()
	editing.value = true
}

function applyTemplate(template) {
	form.subject = template.subject
	form.body_html = template.html
}

function editCampaign(campaign) {
	editing.value = true
	editingId.value = campaign.id
	audiencePreview.value = null
	const segment = campaign.segment || {}
	Object.assign(form, {
		name: campaign.name || '',
		subject: campaign.subject || '',
		body_html: campaign.body_html || (campaign.body ? `<p>${escapeHtml(campaign.body)}</p>` : ''),
		verified_only: segment.verified_only !== false,
		active_mode: segment.active === false ? 'inactive' : segment.active === true ? 'active' : 'all',
		roles: [...(segment.roles || [])],
		tariff_codes: [...(segment.tariff_codes || [])],
		subscription_statuses: [...(segment.subscription_statuses || [])],
	})
	window.scrollTo({ top: 0, behavior: 'smooth' })
}

async function loadMeta() {
	const { data } = await CP_Mail.getMeta()
	if (data?.status !== 'success') throw new Error(data?.error?.message || 'Не удалось загрузить настройки почты')
	meta.value = {
		roles: data.roles || [],
		tariffs: data.tariffs || [],
		subscription_statuses: data.subscription_statuses || [],
		can_manage: Boolean(data.can_manage),
		gateway: data.gateway || null,
	}
	fillGatewayForm(data.gateway || {})
}

function fillGatewayForm(gateway) {
	Object.assign(gatewayForm, {
		provider: gateway.provider || 'smtp',
		enabled: Boolean(gateway.enabled),
		host: gateway.host || '',
		port: Number(gateway.port || 587),
		api_base_url: gateway.api_base_url || 'https://api.rusender.ru',
		key_id: gateway.key_id || '',
		api_token: '',
		from_email: gateway.from_email || '',
		from_name: gateway.from_name || 'WB Insight',
		reply_to_email: gateway.reply_to_email || '',
		starttls: gateway.starttls !== false,
		timeout_seconds: Number(gateway.timeout_seconds || 10),
		username: '',
		password: '',
		clear_credentials: false,
	})
}

async function loadCampaigns() {
	loading.value = true
	error.value = ''
	try {
		const params = { limit: campaignLimit, offset: campaignOffset.value }
		if (campaignStatus.value) params.status = campaignStatus.value
		const { data } = await CP_Mail.getCampaigns(params)
		if (data?.status !== 'success' || !Array.isArray(data?.campaigns)) throw new Error('Некорректный ответ API')
		campaigns.value = data.campaigns
		campaignTotal.value = Number(data.total || 0)
		if (selected.value) {
			selected.value = campaigns.value.find((item) => item.id === selected.value.id) || selected.value
		}
	} catch (e) {
		error.value = e.response?.data?.error?.message || e.message || 'Не удалось загрузить рассылки.'
	} finally {
		loading.value = false
	}
}

async function saveCampaign() {
	setMessage('')
	try {
		if (!form.name.trim() || !form.subject.trim() || !form.body_html.trim()) {
			throw new Error('Заполните название кампании, тему и содержимое письма.')
		}
		const payload = {
			name: form.name.trim(),
			subject: form.subject.trim(),
			body_html: form.body_html,
			segment: segmentPayload(),
		}
		const { data } = editingId.value
			? await CP_Mail.updateCampaign(editingId.value, payload)
			: await CP_Mail.createCampaign(payload)
		if (data?.status !== 'success' || !data?.campaign) throw new Error(data?.error?.message || 'Не удалось сохранить рассылку')
		const campaign = data.campaign
		resetEditor()
		campaignOffset.value = 0
		campaignStatus.value = ''
		await loadCampaigns()
		await openCampaign(campaign)
		setMessage('Черновик сохранён.')
	} catch (e) {
		setMessage(e.response?.data?.error?.message || e.message || 'Не удалось сохранить рассылку.', true)
	}
}

async function previewAudienceForForm() {
	setMessage('')
	try {
		const { data } = await CP_Mail.previewAudience(segmentPayload())
		if (data?.status !== 'success') throw new Error(data?.error?.message || 'Не удалось рассчитать аудиторию')
		audiencePreview.value = data
	} catch (e) {
		setMessage(e.response?.data?.error?.message || e.message || 'Не удалось рассчитать аудиторию.', true)
	}
}

async function applyCampaignFilter() {
	campaignOffset.value = 0
	await loadCampaigns()
}

async function campaignPageDelta(delta) {
	const next = campaignOffset.value + delta * campaignLimit
	if (next < 0 || next >= campaignTotal.value) return
	campaignOffset.value = next
	await loadCampaigns()
}

async function loadMessages() {
	if (!selected.value) return
	try {
		const params = { limit: messageLimit, offset: messageOffset.value }
		if (messageStatus.value) params.status = messageStatus.value
		const { data } = await CP_Mail.getMessages(selected.value.id, params)
		if (data?.status !== 'success' || !Array.isArray(data?.messages)) throw new Error('Некорректный ответ API')
		messages.value = data.messages
		messageTotal.value = Number(data.total || 0)
	} catch (e) {
		setMessage(e.response?.data?.error?.message || 'Не удалось загрузить журнал доставки.', true)
	}
}

async function openCampaign(campaign) {
	selected.value = campaign
	audiencePreview.value = null
	messages.value = []
	messageOffset.value = 0
	messageStatus.value = ''
	scheduleAt.value = ''
	try {
		const { data: detail } = await CP_Mail.getCampaign(campaign.id)
		if (detail?.campaign) selected.value = detail.campaign
		await loadMessages()
	} catch (e) {
		setMessage(e.response?.data?.error?.message || 'Не удалось открыть рассылку.', true)
	}
}

async function applyMessageFilter() {
	messageOffset.value = 0
	await loadMessages()
}

async function messagePageDelta(delta) {
	const next = messageOffset.value + delta * messageLimit
	if (next < 0 || next >= messageTotal.value) return
	messageOffset.value = next
	await loadMessages()
}

async function previewSelectedAudience() {
	if (!selected.value) return
	try {
		const { data } = await CP_Mail.previewCampaign(selected.value.id)
		audiencePreview.value = data
	} catch (e) {
		setMessage(e.response?.data?.error?.message || 'Не удалось рассчитать аудиторию.', true)
	}
}

async function sendTest() {
	if (!selected.value || !testEmail.value) return
	try {
		const { data } = await CP_Mail.testSend(selected.value.id, testEmail.value)
		if (data?.status !== 'success') throw new Error(data?.error?.message || 'Не удалось поставить тест в очередь')
		setMessage('Тестовое письмо поставлено в очередь.')
	} catch (e) {
		setMessage(e.response?.data?.error?.message || e.message || 'Не удалось поставить тестовое письмо в очередь.', true)
	}
}

async function scheduleCampaign() {
	if (!selected.value || !scheduleAt.value) return
	try {
		const launchAt = new Date(scheduleAt.value)
		if (Number.isNaN(launchAt.getTime())) throw new Error('Укажите дату и время запуска.')
		const { data } = await CP_Mail.schedule(selected.value.id, launchAt.toISOString())
		if (data?.campaign) selected.value = data.campaign
		scheduleAt.value = ''
		await loadCampaigns()
		setMessage('Рассылка запланирована.')
	} catch (e) {
		setMessage(e.response?.data?.error?.message || e.message || 'Не удалось запланировать рассылку.', true)
	}
}

function requestConfirmation(action) {
	if (selected.value) confirmAction.value = action
}

async function launchCampaign() {
	if (!selected.value) return
	try {
		const { data } = await CP_Mail.launch(selected.value.id)
		if (data?.campaign) selected.value = data.campaign
		await loadCampaigns()
		messageOffset.value = 0
		await loadMessages()
		setMessage('Рассылка поставлена в очередь.')
	} catch (e) {
		setMessage(e.response?.data?.error?.message || 'Не удалось запустить рассылку.', true)
	}
}

async function cancelCampaign() {
	if (!selected.value) return
	try {
		const { data } = await CP_Mail.cancel(selected.value.id)
		if (data?.campaign) selected.value = data.campaign
		await loadCampaigns()
		await loadMessages()
		setMessage('Рассылка остановлена.')
	} catch (e) {
		setMessage(e.response?.data?.error?.message || 'Не удалось остановить рассылку.', true)
	}
}

async function confirmPendingAction() {
	const action = confirmAction.value
	confirmAction.value = null
	if (action === 'launch') await launchCampaign()
	if (action === 'cancel') await cancelCampaign()
}

async function saveGateway() {
	gatewayBusy.value = true
	setMessage('')
	try {
		const payload = {
			provider: gatewayForm.provider,
			enabled: gatewayForm.provider === 'smtp' ? gatewayForm.enabled : false,
			from_email: gatewayForm.from_email,
			from_name: gatewayForm.from_name,
			reply_to_email: gatewayForm.provider === 'smtp' ? gatewayForm.reply_to_email : '',
			timeout_seconds: gatewayForm.timeout_seconds,
			clear_credentials: gatewayForm.clear_credentials,
		}
		if (gatewayForm.provider === 'smtp') {
			payload.host = gatewayForm.host
			payload.port = gatewayForm.port
			payload.starttls = gatewayForm.starttls
			if (gatewayForm.username) payload.username = gatewayForm.username
			if (gatewayForm.password) payload.password = gatewayForm.password
		} else {
			payload.api_base_url = gatewayForm.api_base_url || 'https://api.rusender.ru'
			payload.key_id = gatewayForm.key_id
			if (gatewayForm.api_token) payload.api_token = gatewayForm.api_token
		}
		const { data } = await CP_Mail.updateGateway(payload)
		if (data?.status !== 'success') throw new Error(data?.error?.message || 'Не удалось сохранить транспорт')
		meta.value.gateway = data.gateway
		fillGatewayForm(data.gateway)
		setMessage('Настройки почтового шлюза сохранены.')
	} catch (e) {
		setMessage(e.response?.data?.error?.message || e.message || 'Не удалось сохранить почтовый шлюз.', true)
	} finally {
		gatewayBusy.value = false
	}
}

async function testGateway() {
	if (!gatewayTestEmail.value) return
	gatewayBusy.value = true
	try {
		const { data } = await CP_Mail.testGateway(gatewayTestEmail.value)
		if (data?.status !== 'success') throw new Error(data?.error?.message || 'Mail transport test failed')
		setMessage('Тестовое письмо отправлено через текущий почтовый транспорт.')
	} catch (e) {
		setMessage(e.response?.data?.error?.message || e.message || 'Не удалось отправить тестовое письмо.', true)
	} finally {
		gatewayBusy.value = false
	}
}

const statusLabel = (value) => ({
	draft: 'Черновик', scheduled: 'Запланирована', queued: 'В очереди', sending: 'Отправляется',
	completed: 'Завершена', failed: 'С ошибками', cancelled: 'Отменена',
}[value] || value)

const formatDate = (value) => value ? new Date(value).toLocaleString('ru-RU') : '—'

onMounted(async () => {
	try {
		await loadMeta()
		await loadCampaigns()
	} catch (e) {
		error.value = e.response?.data?.error?.message || e.message || 'Не удалось загрузить почтовый модуль.'
	}
})
</script>

<template>
	<section class="cp-page mail-page">
		<header class="cp-page-header mail-header">
			<div>
				<p class="cp-eyebrow">Коммуникации</p>
				<h2 class="cp-detail-title">Рассылки</h2>
				<p class="cp-subtitle">Создание писем, аудитория, доставка и единый почтовый шлюз WB Insight.</p>
			</div>
			<BaseButton v-if="activeTab === 'campaigns' && canManage" variant="primary" text="Создать рассылку" @click="newCampaign" />
		</header>

		<nav class="mail-tabs" aria-label="Разделы почты">
			<button type="button" :class="{ active: activeTab === 'campaigns' }" @click="activeTab = 'campaigns'">Кампании</button>
			<button type="button" :class="{ active: activeTab === 'gateway' }" @click="activeTab = 'gateway'">
				Почтовый шлюз
				<span class="gateway-dot" :class="{ ready: meta.gateway?.ready }" />
			</button>
		</nav>

		<div v-if="actionMessage" class="cp-state" :class="{ 'cp-state--error': actionIsError }">{{ actionMessage }}</div>
		<div v-if="error" class="cp-state cp-state--error">{{ error }}</div>

		<template v-if="activeTab === 'campaigns'">
			<Transition name="cp-expand">
				<section v-if="editing && canManage" class="cp-card campaign-editor-card">
					<div class="editor-head">
						<div>
							<p class="cp-eyebrow">{{ editingId ? 'Редактирование' : 'Новая кампания' }}</p>
							<h3>{{ editingId ? 'Измените письмо и аудиторию' : 'Соберите письмо' }}</h3>
							<p class="cp-card-note">Черновик можно менять до запуска. После запуска аудитория и содержимое фиксируются.</p>
						</div>
						<BaseButton variant="outline" text="Закрыть редактор" @click="resetEditor" />
					</div>

					<div class="starter-row">
						<span>Быстрый старт:</span>
						<button v-for="template in starterTemplates" :key="template.code" type="button" @click="applyTemplate(template)">
							{{ template.name }}
						</button>
					</div>

					<div class="campaign-fields">
						<label>
							<span>Название кампании</span>
							<input v-model.trim="form.name" maxlength="180" placeholder="Например: Сентябрьское обновление">
							<small>Внутреннее название. Получатель его не увидит.</small>
						</label>
						<label>
							<span>Тема письма</span>
							<input v-model.trim="form.subject" maxlength="255" placeholder="Что увидит получатель во входящих">
							<small>Короткая тема обычно читается лучше на мобильном.</small>
						</label>
					</div>

					<div>
						<div class="section-caption">
							<div>
								<strong>Содержание письма</strong>
								<span>Оформляйте письмо визуально; HTML будет очищен backend-ом перед сохранением и отправкой.</span>
							</div>
						</div>
						<MailComposer v-model="form.body_html" />
					</div>

					<section class="audience-builder">
						<div class="section-caption">
							<div>
								<strong>Кому отправить</strong>
								<span>Если роли или тарифы не выбраны, фильтр по ним не применяется. Получатель должен пройти все выбранные фильтры.</span>
							</div>
							<BaseButton variant="outline" size="small" text="Рассчитать аудиторию" @click="previewAudienceForForm" />
						</div>

						<div class="audience-basics">
							<label class="toggle-line"><input v-model="form.verified_only" type="checkbox"> Только подтверждённые email</label>
							<label>
								<span>Состояние аккаунта</span>
								<select v-model="form.active_mode">
									<option value="active">Только активные</option>
									<option value="all">Все</option>
									<option value="inactive">Только деактивированные</option>
								</select>
							</label>
						</div>

						<div class="audience-groups">
							<fieldset>
								<legend>Роли пользователей</legend>
								<p>Например, <strong>user</strong> — клиенты, <strong>manager</strong> — сотрудники с ролью менеджера.</p>
								<div class="choice-grid">
									<label v-for="role in meta.roles" :key="role" class="choice-chip">
										<input v-model="form.roles" type="checkbox" :value="role">
										<span>{{ roleLabels[role] || role }}</span>
									</label>
								</div>
							</fieldset>

							<fieldset>
								<legend>Тарифы</legend>
								<p>Фильтр выбирает пользователей по текущей подписке на конкретный тариф.</p>
								<div class="choice-grid">
									<label v-for="tariff in meta.tariffs" :key="tariff.id" class="choice-chip">
										<input v-model="form.tariff_codes" type="checkbox" :value="tariff.code">
										<span>{{ tariff.name }} <small>{{ tariff.code }}</small></span>
									</label>
								</div>
							</fieldset>

							<fieldset>
								<legend>Статус подписки</legend>
								<p>Позволяет, например, отдельно обратиться к DEMO-пользователям или активным платным клиентам.</p>
								<div class="choice-grid">
									<label v-for="status in meta.subscription_statuses" :key="status" class="choice-chip">
										<input v-model="form.subscription_statuses" type="checkbox" :value="status">
										<span>{{ subscriptionLabels[status] || status }}</span>
									</label>
								</div>
							</fieldset>
						</div>

						<div v-if="audiencePreview" class="audience-preview">
							<div><strong>{{ audiencePreview.deliverable_count }}</strong><span>получат письмо</span></div>
							<div><strong>{{ audiencePreview.audience_count }}</strong><span>подходят под фильтр</span></div>
							<div><strong>{{ audiencePreview.suppressed_count }}</strong><span>исключены из рассылок</span></div>
							<div v-if="audiencePreview.sample?.length" class="audience-sample">
								<span>Пример:</span>
								<code v-for="item in audiencePreview.sample" :key="item.id">{{ item.email }}</code>
							</div>
						</div>
					</section>

					<div class="editor-actions">
						<BaseButton variant="primary" text="Сохранить черновик" @click="saveCampaign" />
						<BaseButton variant="outline" text="Отмена" @click="resetEditor" />
					</div>
				</section>
			</Transition>

			<div class="mail-toolbar">
				<label>Статус кампании
					<select v-model="campaignStatus" @change="applyCampaignFilter">
						<option value="">Все</option>
						<option value="draft">Черновики</option>
						<option value="scheduled">Запланированные</option>
						<option value="queued">В очереди</option>
						<option value="sending">Отправляются</option>
						<option value="completed">Завершённые</option>
						<option value="failed">С ошибками</option>
						<option value="cancelled">Отменённые</option>
					</select>
				</label>
			</div>

			<div v-if="loading" class="cp-state" role="status">Загружаем рассылки…</div>
			<div v-else class="mail-layout">
				<div class="cp-card mail-list">
					<div class="mail-list__head"><h3>Кампании</h3><span class="cp-chip">{{ campaignTotal }}</span></div>
					<div v-if="campaigns.length === 0" class="cp-state">Рассылок пока нет.</div>
					<button v-for="campaign in campaigns" :key="campaign.id" type="button" class="campaign-row" :class="{ active: selected?.id === campaign.id }" @click="openCampaign(campaign)">
						<div><strong>{{ campaign.name }}</strong><span>{{ campaign.subject }}</span><small v-if="campaign.scheduled_at">Старт: {{ formatDate(campaign.scheduled_at) }}</small></div>
						<div class="campaign-row__meta"><span class="cp-chip">{{ statusLabel(campaign.status) }}</span><small>{{ campaign.sent_count }}/{{ campaign.audience_count }}</small></div>
					</button>
					<div v-if="campaignTotal > campaignLimit" class="mail-pagination">
						<BaseButton variant="outline" text="Назад" :disabled="campaignOffset === 0" @click="campaignPageDelta(-1)" />
						<span>{{ campaignPage }} / {{ campaignPages }}</span>
						<BaseButton variant="outline" text="Далее" :disabled="campaignOffset + campaignLimit >= campaignTotal" @click="campaignPageDelta(1)" />
					</div>
				</div>

				<div v-if="selected" class="cp-card mail-detail">
					<div class="mail-detail__head">
						<div><p class="cp-eyebrow">Кампания</p><h3>{{ selected.name }}</h3><p class="cp-card-note">{{ selected.subject }}</p><p v-if="selected.scheduled_at" class="cp-card-note">Запланирована на {{ formatDate(selected.scheduled_at) }}</p></div>
						<div class="detail-head-actions">
							<span class="cp-chip">{{ statusLabel(selected.status) }}</span>
							<BaseButton v-if="canManage && ['draft','scheduled'].includes(selected.status)" variant="outline" size="small" text="Редактировать" @click="editCampaign(selected)" />
						</div>
					</div>
					<div class="mail-stats"><div><span>Аудитория</span><strong>{{ selected.audience_count }}</strong></div><div><span>Отправлено</span><strong>{{ selected.sent_count }}</strong></div><div><span>Ошибки</span><strong>{{ selected.failed_count }}</strong></div><div><span>Исключено</span><strong>{{ selected.suppressed_count }}</strong></div></div>

					<div class="campaign-preview-frame">
						<iframe title="Предпросмотр кампании" sandbox="" :srcdoc="selectedPreviewDocument" />
					</div>

					<div v-if="canManage && ['draft','scheduled'].includes(selected.status)" class="cp-actions mail-launch-actions">
						<BaseButton variant="outline" text="Рассчитать аудиторию" @click="previewSelectedAudience" />
						<BaseButton variant="primary" text="Запустить сейчас" :disabled="!meta.gateway?.marketing_ready" @click="requestConfirmation('launch')" />
					</div>
					<div v-if="!meta.gateway?.marketing_ready" class="cp-info-callout">
						<strong>Маркетинговая отправка пока недоступна.</strong>
						<span>Нужны готовый SMTP, включённые кампании и безопасный one-click unsubscribe. Проверьте вкладку «Почтовый шлюз».</span>
					</div>
					<div v-if="canManage && ['draft','scheduled'].includes(selected.status)" class="mail-schedule">
						<label>Запланировать запуск<input v-model="scheduleAt" type="datetime-local" :min="minScheduleAt"></label>
						<BaseButton variant="outline" text="Запланировать" :disabled="!scheduleAt || !meta.gateway?.marketing_ready" @click="scheduleCampaign" />
					</div>
					<div v-if="canManage && !['draft','completed','cancelled','failed'].includes(selected.status)" class="cp-actions"><BaseButton variant="outline" text="Остановить" @click="requestConfirmation('cancel')" /></div>
					<div v-if="canManage" class="mail-test"><input v-model.trim="testEmail" type="email" placeholder="Email для тестового письма"><BaseButton variant="outline" text="Отправить тест" :disabled="!testEmail || !meta.gateway?.ready || !meta.gateway?.enabled" @click="sendTest" /></div>

					<div v-if="audiencePreview" class="audience-preview compact">
						<div><strong>{{ audiencePreview.deliverable_count }}</strong><span>получат письмо</span></div>
						<div><strong>{{ audiencePreview.suppressed_count }}</strong><span>исключены</span></div>
					</div>

					<div class="mail-delivery-head"><h4>Доставка</h4><select v-model="messageStatus" @change="applyMessageFilter"><option value="">Все статусы</option><option value="queued">В очереди</option><option value="sending">Отправляется</option><option value="sent">Отправлено</option><option value="failed">Ошибка</option><option value="suppressed">Исключено</option><option value="cancelled">Отменено</option></select></div>
					<div v-if="messages.length === 0" class="cp-state">Сообщений ещё нет.</div>
					<div v-else class="cp-table-scroll"><table class="cp-table"><thead><tr><th>Email</th><th>Статус</th><th>Попытки</th><th>Ошибка</th><th>Отправлено</th></tr></thead><tbody><tr v-for="item in messages" :key="item.id"><td>{{ item.recipient_email }}</td><td>{{ item.status }}</td><td>{{ item.attempt_count }}/{{ item.max_attempts }}</td><td>{{ item.safe_error_code || '—' }}</td><td>{{ formatDate(item.sent_at) }}</td></tr></tbody></table></div>
					<div v-if="messageTotal > messageLimit" class="mail-pagination"><BaseButton variant="outline" text="Назад" :disabled="messageOffset === 0" @click="messagePageDelta(-1)" /><span>{{ messagePage }} / {{ messagePages }} · {{ messageTotal }}</span><BaseButton variant="outline" text="Далее" :disabled="messageOffset + messageLimit >= messageTotal" @click="messagePageDelta(1)" /></div>
				</div>
				<div v-else class="cp-state">Выберите рассылку слева или создайте новую.</div>
			</div>
		</template>

		<template v-else>
			<section class="gateway-grid">
				<article class="cp-card gateway-status-card">
					<div class="gateway-status-head">
						<div>
							<p class="cp-eyebrow">Транспорт</p>
							<h3>{{ meta.gateway?.provider === 'rusender' ? 'RuSender API' : 'SMTP' }}</h3>
						</div>
						<span class="cp-chip" :class="meta.gateway?.ready ? 'cp-chip--active' : 'cp-chip--inactive'">
							{{ meta.gateway?.ready ? 'Готов' : 'Не готов' }}
						</span>
					</div>
					<dl>
						<div><dt>Источник</dt><dd>{{ meta.gateway?.source || '—' }}</dd></div>
						<div><dt>Системная почта</dt><dd>{{ meta.gateway?.ready ? 'Готова' : 'Не готова' }}</dd></div>
						<div><dt>Кампании</dt><dd>{{ meta.gateway?.marketing_ready ? 'Готовы' : 'Выключены' }}</dd></div>
						<div><dt>Credentials</dt><dd>{{ meta.gateway?.credentials_configured ? 'Настроены' : 'Не настроены' }}</dd></div>
						<div v-if="meta.gateway?.provider === 'rusender'"><dt>Key ID</dt><dd>{{ meta.gateway?.key_id || '—' }}</dd></div>
						<div v-else><dt>Пользователь</dt><dd>{{ meta.gateway?.username_hint || '—' }}</dd></div>
					</dl>
					<p v-if="meta.gateway?.provider === 'rusender'" class="cp-card-note">
						RuSender работает по HTTPS и не зависит от исходящих SMTP-портов хостера. Этот адаптер сейчас используется для подтверждения email, recovery и системных писем. Маркетинговые кампании через него намеренно не включаются.
					</p>
					<p v-else class="cp-card-note">
						SMTP используется и для системной почты, и для пользовательских кампаний. Пароль после сохранения обратно в браузер не возвращается.
					</p>
				</article>

				<form v-if="canManage && meta.gateway?.editable" class="cp-card gateway-form" @submit.prevent="saveGateway">
					<div class="gateway-form-head">
						<div><p class="cp-eyebrow">Настройка</p><h3>Почтовый шлюз</h3></div>
					</div>

					<div class="provider-choice" role="radiogroup" aria-label="Тип почтового транспорта">
						<label :class="{ active: gatewayForm.provider === 'rusender' }">
							<input v-model="gatewayForm.provider" type="radio" value="rusender">
							<span><strong>RuSender API</strong><small>HTTPS :443 · системные письма</small></span>
						</label>
						<label :class="{ active: gatewayForm.provider === 'smtp' }">
							<input v-model="gatewayForm.provider" type="radio" value="smtp">
							<span><strong>SMTP</strong><small>Классический почтовый шлюз</small></span>
						</label>
					</div>

					<div v-if="gatewayForm.provider === 'rusender'" class="gateway-fields">
						<label class="wide"><span>API endpoint</span><input value="https://api.rusender.ru" disabled></label>
						<label><span>Key ID</span><input v-model.trim="gatewayForm.key_id" inputmode="numeric" placeholder="15074"></label>
						<label><span>Timeout, сек.</span><input v-model.number="gatewayForm.timeout_seconds" type="number" min="1" max="120"></label>
						<label><span>Имя отправителя</span><input v-model.trim="gatewayForm.from_name" maxlength="160" placeholder="WB Insight"></label>
						<label><span>Email отправителя</span><input v-model.trim="gatewayForm.from_email" type="email" placeholder="no-reply@mail.jsinteractive.ru"></label>
						<label class="wide"><span>API token</span><input v-model="gatewayForm.api_token" type="password" autocomplete="new-password" :placeholder="meta.gateway?.credentials_configured && meta.gateway?.provider === 'rusender' ? 'Пусто = оставить текущий токен' : 'rs_ck_v1_…'"></label>
						<label class="switch-line wide danger-toggle"><input v-model="gatewayForm.clear_credentials" type="checkbox"> Очистить сохранённый API token</label>
					</div>

					<div v-else class="gateway-fields">
						<label class="wide"><span>SMTP host</span><input v-model.trim="gatewayForm.host" placeholder="smtp.provider.ru"></label>
						<label><span>Port</span><input v-model.number="gatewayForm.port" type="number" min="1" max="65535"></label>
						<label><span>Timeout, сек.</span><input v-model.number="gatewayForm.timeout_seconds" type="number" min="1" max="120"></label>
						<label><span>Имя отправителя</span><input v-model.trim="gatewayForm.from_name" maxlength="160" placeholder="WB Insight"></label>
						<label><span>Email отправителя</span><input v-model.trim="gatewayForm.from_email" type="email" placeholder="news@jsinteractive.ru"></label>
						<label class="wide"><span>Reply-To</span><input v-model.trim="gatewayForm.reply_to_email" type="email" placeholder="support@jsinteractive.ru"></label>
						<label class="switch-line wide"><input v-model="gatewayForm.starttls" type="checkbox"> Использовать STARTTLS</label>
						<label><span>Логин</span><input v-model.trim="gatewayForm.username" autocomplete="off" :placeholder="meta.gateway?.credentials_configured && meta.gateway?.provider === 'smtp' ? 'Пусто = оставить текущий' : 'SMTP username'"></label>
						<label><span>Пароль</span><input v-model="gatewayForm.password" type="password" autocomplete="new-password" :placeholder="meta.gateway?.credentials_configured && meta.gateway?.provider === 'smtp' ? 'Пусто = оставить текущий' : 'SMTP password'"></label>
						<label class="switch-line wide danger-toggle"><input v-model="gatewayForm.clear_credentials" type="checkbox"> Очистить сохранённые credentials</label>
						<label class="switch-line wide"><input v-model="gatewayForm.enabled" type="checkbox"> Разрешить пользовательские кампании</label>
					</div>

					<div class="cp-info-callout">
						<strong>Секреты хранятся зашифрованно.</strong>
						<span v-if="gatewayForm.provider === 'rusender'">API token шифруется сервером и после сохранения никогда не возвращается в браузер. Для текущего ключа отправки укажите Key ID 15074 и адрес на домене mail.jsinteractive.ru.</span>
						<span v-else>Пароль SMTP шифруется сервером ключом приложения и никогда не возвращается через API после сохранения.</span>
					</div>

					<div v-if="gatewayForm.provider === 'rusender'" class="cp-info-callout">
						<strong>Кампании пока остаются на SMTP-транспорте.</strong>
						<span>Транзакционный RuSender API документирует только X-* custom headers, поэтому мы не заявляем через него RFC 8058 one-click unsubscribe. Verification/recovery и системные письма работают через RuSender уже сейчас.</span>
					</div>

					<div class="editor-actions">
						<BaseButton type="submit" variant="primary" text="Сохранить шлюз" loading-text="Сохраняем…" :loading="gatewayBusy" />
					</div>
				</form>

				<div v-else-if="canManage" class="cp-card gateway-form">
					<div class="cp-info-callout">
						<strong>Почтовый транспорт сейчас управляется переменными окружения.</strong>
						<span>Чтобы редактировать шлюз из панели, установите <code>MAIL_CONFIG_SOURCE=auto</code> или <code>MAIL_CONFIG_SOURCE=database</code> и перезапустите backend.</span>
					</div>
				</div>
			</section>

			<section class="cp-card deliverability-card">
				<div class="section-caption">
					<div>
						<p class="cp-eyebrow">Доставляемость</p>
						<h3>Защита от спама и подмены отправителя</h3>
						<span>Часть требований контролирует приложение, SPF/DKIM/DMARC/PTR настраиваются у DNS/SMTP-провайдера.</span>
					</div>
				</div>
				<div class="deliverability-grid">
					<div :class="{ ok: meta.gateway?.deliverability?.tls }"><strong>STARTTLS</strong><span>{{ meta.gateway?.deliverability?.tls ? 'Включён' : 'Требует настройки' }}</span></div>
					<div :class="{ ok: meta.gateway?.deliverability?.sender_identity }"><strong>From identity</strong><span>{{ meta.gateway?.deliverability?.sender_identity ? 'Настроен' : 'Требует настройки' }}</span></div>
					<div :class="{ ok: meta.gateway?.deliverability?.one_click_unsubscribe }"><strong>One-click unsubscribe</strong><span>{{ meta.gateway?.deliverability?.one_click_unsubscribe ? 'Готов' : 'Нужны MAIL_UNSUBSCRIBE_BASE_URL + HMAC key' }}</span></div>
					<div :class="{ ok: meta.gateway?.deliverability?.reply_to_configured }"><strong>Reply-To</strong><span>{{ meta.gateway?.deliverability?.reply_to_configured ? 'Настроен' : 'Рекомендуется' }}</span></div>
					<div class="external"><strong>SPF</strong><span>Проверить DNS</span></div>
					<div class="external"><strong>DKIM</strong><span>Включить у SMTP-провайдера</span></div>
					<div class="external"><strong>DMARC</strong><span>Проверить DNS</span></div>
					<div class="external"><strong>PTR / rDNS</strong><span>Проверить у провайдера IP</span></div>
				</div>
				<div class="cp-info-callout">
					<strong>Для маркетинговых писем приложение добавляет служебные заголовки автоматически.</strong>
					<span>Date, Message-ID, Reply-To, List-ID, List-Unsubscribe, List-Unsubscribe-Post и Precedence: bulk. Транзакционные письма подтверждения и recovery не помечаются как bulk. Безопасная подпись отписки задаётся на сервере через MAIL_UNSUBSCRIBE_HMAC_KEY.</span>
				</div>
			</section>

			<section class="cp-card gateway-test-card">
				<div>
					<p class="cp-eyebrow">Проверка</p>
					<h3>Отправить тестовое письмо</h3>
					<p class="cp-card-note">Тест идёт напрямую через текущую эффективную SMTP-конфигурацию и помогает проверить host, STARTTLS и credentials до запуска кампаний.</p>
				</div>
				<div class="gateway-test-action">
					<input v-model.trim="gatewayTestEmail" type="email" placeholder="your@email.com">
					<BaseButton variant="outline" text="Отправить тест" loading-text="Отправляем…" :loading="gatewayBusy" :disabled="!gatewayTestEmail || !meta.gateway?.ready" @click="testGateway" />
				</div>
			</section>
		</template>

		<Modal :is-open="Boolean(confirmAction)" size="small" :close-on-overlay-click="true" @close="confirmAction = null">
			<template #header><h3>{{ confirmTitle }}</h3></template>
			<template #body><p class="mail-confirm__text">{{ confirmText }}</p></template>
			<template #footer><div class="cp-actions"><BaseButton variant="outline" text="Отмена" @click="confirmAction = null" /><BaseButton variant="primary" :text="confirmAction === 'cancel' ? 'Остановить' : 'Запустить'" @click="confirmPendingAction" /></div></template>
		</Modal>
	</section>
</template>

<style scoped>
.mail-page { gap: 16px; }
.mail-header { display:flex; align-items:flex-end; justify-content:space-between; gap:20px; }
.mail-tabs {
	display:flex; gap:6px; padding:6px; width:fit-content;
	border:1px solid var(--border-color); border-radius:11px; background:var(--card-bg);
}
.mail-tabs button {
	display:flex; align-items:center; gap:8px; min-height:36px; padding:7px 12px;
	border:0; border-radius:8px; background:transparent; color:var(--text-muted); font:inherit; font-weight:700; cursor:pointer;
}
.mail-tabs button.active { background:color-mix(in srgb,var(--secondary-color) 10%,var(--card-bg)); color:var(--secondary-color); }
.gateway-dot { width:7px; height:7px; border-radius:50%; background:var(--danger-color); }
.gateway-dot.ready { background:var(--success-color); }

.campaign-editor-card { padding:22px; display:grid; gap:20px; }
.editor-head,.section-caption,.gateway-form-head,.gateway-status-head,.mail-list__head,.mail-detail__head,.mail-delivery-head {
	display:flex; justify-content:space-between; align-items:flex-start; gap:14px;
}
.editor-head h3,.gateway-form h3,.gateway-status-card h3,.gateway-test-card h3,.mail-detail h3,.mail-list h3 { margin:2px 0 0; }
.section-caption > div { display:grid; gap:3px; }
.section-caption span { color:var(--text-subtle); font-size:12px; }
.starter-row { display:flex; flex-wrap:wrap; align-items:center; gap:8px; color:var(--text-muted); font-size:12px; }
.starter-row button {
	padding:7px 10px; border:1px solid var(--border-color); border-radius:8px; background:var(--light-bg); color:var(--text-color); cursor:pointer;
}
.starter-row button:hover { background:var(--hover-bg); }

.campaign-fields { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
.campaign-fields label,.gateway-fields label,.audience-basics label,.mail-toolbar label,.mail-schedule label {
	display:grid; gap:6px; color:var(--text-muted); font-size:12px; font-weight:650;
}
.campaign-fields input,.gateway-fields input,.audience-basics select,.mail-toolbar select,.mail-schedule input,.mail-test input,.mail-delivery-head select,.gateway-test-action input {
	box-sizing:border-box; width:100%; min-height:40px; padding:8px 10px;
	border:1px solid var(--border-color); border-radius:8px; background:var(--light-bg); color:var(--text-color);
}
.campaign-fields small { color:var(--text-subtle); font-weight:400; }

.audience-builder { display:grid; gap:14px; padding:18px; border:1px solid var(--border-color); border-radius:12px; background:var(--light-bg); }
.audience-basics { display:grid; grid-template-columns:1fr 240px; gap:12px; align-items:end; }
.toggle-line,.switch-line { display:flex !important; align-items:center; gap:8px; }
.toggle-line input,.switch-line input,.choice-chip input { width:auto; min-height:0; }
.audience-groups { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; }
.audience-groups fieldset {
	min-width:0; margin:0; padding:14px; border:1px solid var(--border-color); border-radius:10px; background:var(--card-bg);
}
.audience-groups legend { padding:0 5px; font-weight:750; }
.audience-groups p { min-height:36px; margin:4px 0 10px; color:var(--text-subtle); font-size:11px; line-height:1.45; }
.choice-grid { display:flex; flex-wrap:wrap; gap:7px; }
.choice-chip {
	display:inline-flex; align-items:center; gap:6px; padding:7px 9px;
	border:1px solid var(--border-color); border-radius:999px; background:var(--light-bg); color:var(--text-color); font-size:12px; cursor:pointer;
}
.choice-chip:has(input:checked) { border-color:color-mix(in srgb,var(--secondary-color) 45%,var(--border-color)); background:color-mix(in srgb,var(--secondary-color) 10%,var(--card-bg)); }
.choice-chip small { color:var(--text-subtle); }
.audience-preview {
	display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:8px;
	padding:12px; border:1px solid color-mix(in srgb,var(--secondary-color) 20%,var(--border-color)); border-radius:10px; background:color-mix(in srgb,var(--secondary-color) 6%,var(--card-bg));
}
.audience-preview.compact { grid-template-columns:repeat(2,minmax(0,180px)); margin:14px 0; }
.audience-preview > div { display:grid; gap:2px; }
.audience-preview strong { font-size:20px; }
.audience-preview span { color:var(--text-muted); font-size:11px; }
.audience-sample { grid-column:1/-1 !important; display:flex !important; flex-wrap:wrap; align-items:center; gap:6px !important; }
.audience-sample code { padding:4px 6px; border-radius:6px; background:var(--light-bg); }
.editor-actions { display:flex; gap:8px; }

.mail-toolbar { display:flex; justify-content:flex-end; }
.mail-layout { display:grid; grid-template-columns:minmax(270px,.66fr) minmax(0,1.34fr); gap:16px; align-items:start; }
.mail-list,.mail-detail { padding:20px; }
.campaign-row {
	width:100%; display:flex; justify-content:space-between; gap:12px; padding:14px 8px;
	border:0; border-top:1px solid var(--border-color); border-radius:8px; background:transparent; color:var(--text-color); text-align:left; cursor:pointer;
	transition:background 220ms ease,transform 220ms ease;
}
.campaign-row:hover { background:var(--hover-bg); }
.campaign-row.active { background:color-mix(in srgb,var(--secondary-color) 10%,var(--card-bg)); }
.campaign-row div:first-child { display:grid; gap:4px; }
.campaign-row span,.campaign-row small { color:var(--text-muted); }
.campaign-row__meta { display:grid; justify-items:end; gap:6px; }
.detail-head-actions { display:flex; align-items:center; gap:8px; }
.mail-stats { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:8px; margin:18px 0 12px; }
.mail-stats div { padding:11px; display:grid; gap:3px; border:1px solid var(--border-color); border-radius:9px; background:var(--light-bg); }
.mail-stats span { color:var(--text-muted); font-size:11px; }
.mail-stats strong { font-size:21px; }
.campaign-preview-frame { padding:10px; border:1px solid var(--border-color); border-radius:11px; background:#e9ecf4; }
.campaign-preview-frame iframe { width:100%; height:420px; border:0; border-radius:7px; background:#fff; }
.mail-launch-actions { margin-top:14px; }
.mail-test,.mail-schedule { display:flex; gap:9px; margin:14px 0; align-items:end; }
.mail-test input,.mail-schedule label { flex:1; }
.mail-delivery-head { align-items:center; margin-top:20px; }
.mail-pagination { display:flex; align-items:center; justify-content:center; gap:10px; margin-top:14px; color:var(--text-muted); }

.gateway-grid { display:grid; grid-template-columns:minmax(280px,.65fr) minmax(0,1.35fr); gap:16px; align-items:start; }
.gateway-status-card,.gateway-form,.gateway-test-card { padding:20px; }
.gateway-status-card dl { display:grid; gap:0; margin:18px 0; }
.gateway-status-card dl div { display:flex; justify-content:space-between; gap:12px; padding:10px 0; border-bottom:1px solid var(--border-color); }
.gateway-status-card dt { color:var(--text-muted); }
.gateway-status-card dd { margin:0; font-weight:700; }
.gateway-form { display:grid; gap:16px; }
.gateway-fields { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
.gateway-fields .wide { grid-column:1/-1; }
.danger-toggle { color:var(--danger-color) !important; }
.gateway-test-card { display:flex; align-items:center; justify-content:space-between; gap:20px; }
.gateway-test-action { width:min(520px,100%); display:flex; gap:8px; }
.mail-confirm__text { margin:0; color:var(--text-muted); line-height:1.5; }

.deliverability-card { padding:20px; display:grid; gap:16px; }
.deliverability-card h3 { margin:2px 0 0; }
.deliverability-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:8px; }
.deliverability-grid > div { display:grid; gap:4px; padding:12px; border:1px solid var(--border-color); border-radius:9px; background:var(--light-bg); }
.deliverability-grid strong { font-size:12px; }
.deliverability-grid span { color:var(--text-muted); font-size:11px; }
.deliverability-grid .ok { border-color:color-mix(in srgb,var(--success-color) 32%,var(--border-color)); background:color-mix(in srgb,var(--success-color) 7%,var(--card-bg)); }
.deliverability-grid .external { border-style:dashed; }

@media(max-width:1100px) {
	.audience-groups { grid-template-columns:1fr; }
	.deliverability-grid { grid-template-columns:repeat(2,minmax(0,1fr)); }
	.mail-layout,.gateway-grid { grid-template-columns:1fr; }
}
@media(max-width:760px) {
	.mail-header,.editor-head,.section-caption,.gateway-test-card { align-items:stretch; flex-direction:column; }
	.campaign-fields,.audience-basics { grid-template-columns:1fr; }
	.mail-stats { grid-template-columns:1fr 1fr; }
	.mail-test,.mail-schedule,.gateway-test-action { flex-direction:column; align-items:stretch; }
	.gateway-fields { grid-template-columns:1fr; }
	.gateway-fields .wide { grid-column:auto; }
}
</style>
