<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import CP_Mail from '@/API/ControlPanel/CP_Mail'
import BaseButton from '@/components/UI/Buttons/BaseButton.vue'
import Modal from '@/components/UI/Modal.vue'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
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
const actionError = ref('')
const creating = ref(false)
const preview = ref(null)
const testEmail = ref('')
const scheduleAt = ref('')
const confirmAction = ref(null)

const form = reactive({
	name: '',
	subject: '',
	body: '',
	verified_only: true,
	active: true,
	roles: '',
	tariff_codes: '',
})

const canManage = computed(() => authStore.user?.roles?.includes('super_admin'))
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
	: 'Кампания будет материализована на текущую аудиторию и поставлена в очередь доставки.')

const statusLabel = (value) => ({
	draft: 'Черновик', scheduled: 'Запланирована', queued: 'В очереди', sending: 'Отправляется', completed: 'Завершена', failed: 'С ошибками', cancelled: 'Отменена',
}[value] || value)

const formatDate = (value) => value ? new Date(value).toLocaleString('ru-RU') : '—'

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
		error.value = e.response?.data?.error?.message || 'Не удалось загрузить рассылки.'
	} finally {
		loading.value = false
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

async function createCampaign() {
	actionError.value = ''
	try {
		const segment = {
			verified_only: form.verified_only,
			active: form.active,
			roles: form.roles.split(',').map((v) => v.trim()).filter(Boolean),
			tariff_codes: form.tariff_codes.split(',').map((v) => v.trim()).filter(Boolean),
		}
		const { data } = await CP_Mail.createCampaign({ name: form.name, subject: form.subject, body: form.body, segment })
		if (data?.status !== 'success') throw new Error(data?.error?.message || 'Не удалось создать кампанию')
		creating.value = false
		Object.assign(form, { name: '', subject: '', body: '', verified_only: true, active: true, roles: '', tariff_codes: '' })
		campaignOffset.value = 0
		campaignStatus.value = ''
		await loadCampaigns()
		await openCampaign(data.campaign)
	} catch (e) {
		actionError.value = e.response?.data?.error?.message || e.message || 'Не удалось создать кампанию.'
	}
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
		actionError.value = e.response?.data?.error?.message || 'Не удалось загрузить журнал доставки.'
	}
}

async function openCampaign(campaign) {
	selected.value = campaign
	preview.value = null
	messages.value = []
	messageOffset.value = 0
	messageStatus.value = ''
	scheduleAt.value = ''
	try {
		const { data: detail } = await CP_Mail.getCampaign(campaign.id)
		if (detail?.campaign) selected.value = detail.campaign
		await loadMessages()
	} catch (e) {
		actionError.value = e.response?.data?.error?.message || 'Не удалось открыть рассылку.'
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

async function previewCampaign() {
	if (!selected.value) return
	actionError.value = ''
	try {
		const { data } = await CP_Mail.previewCampaign(selected.value.id)
		if (data?.status !== 'success') throw new Error('Preview failed')
		preview.value = data
	} catch (e) {
		actionError.value = e.response?.data?.error?.message || 'Не удалось рассчитать аудиторию.'
	}
}

async function sendTest() {
	if (!selected.value || !testEmail.value) return
	actionError.value = ''
	try {
		await CP_Mail.testSend(selected.value.id, testEmail.value)
		actionError.value = 'Тестовое письмо поставлено в очередь.'
	} catch (e) {
		actionError.value = e.response?.data?.error?.message || 'Не удалось поставить тестовое письмо в очередь.'
	}
}

async function scheduleCampaign() {
	if (!selected.value || !scheduleAt.value) return
	actionError.value = ''
	try {
		const launchAt = new Date(scheduleAt.value)
		if (Number.isNaN(launchAt.getTime())) throw new Error('Укажите дату и время запуска.')
		const { data } = await CP_Mail.schedule(selected.value.id, launchAt.toISOString())
		if (data?.campaign) selected.value = data.campaign
		scheduleAt.value = ''
		await loadCampaigns()
	} catch (e) {
		actionError.value = e.response?.data?.error?.message || e.message || 'Не удалось запланировать рассылку.'
	}
}

function requestConfirmation(action) {
	if (!selected.value) return
	confirmAction.value = action
}

async function launchCampaign() {
	if (!selected.value) return
	actionError.value = ''
	try {
		const { data } = await CP_Mail.launch(selected.value.id)
		if (data?.campaign) selected.value = data.campaign
		await loadCampaigns()
		messageOffset.value = 0
		await loadMessages()
	} catch (e) {
		actionError.value = e.response?.data?.error?.message || 'Не удалось запустить рассылку.'
	}
}

async function cancelCampaign() {
	if (!selected.value) return
	try {
		const { data } = await CP_Mail.cancel(selected.value.id)
		if (data?.campaign) selected.value = data.campaign
		await loadCampaigns()
		messageOffset.value = 0
		await loadMessages()
	} catch (e) {
		actionError.value = e.response?.data?.error?.message || 'Не удалось остановить рассылку.'
	}
}

async function confirmPendingAction() {
	const action = confirmAction.value
	confirmAction.value = null
	if (action === 'launch') await launchCampaign()
	if (action === 'cancel') await cancelCampaign()
}

onMounted(loadCampaigns)
</script>

<template>
	<section class="cp-page">
		<header class="cp-page-header mail-header">
			<div>
				<p class="cp-eyebrow">Коммуникации</p>
				<h2 class="cp-detail-title">Рассылки</h2>
				<p class="cp-subtitle">Транзакционная почта работает через общую очередь; здесь управляются пользовательские кампании.</p>
			</div>
			<BaseButton v-if="canManage" variant="primary" text="Создать рассылку" @click="creating = !creating" />
		</header>

		<div v-if="actionError" class="cp-state" :class="{ 'cp-state--error': !actionError.includes('поставлено в очередь') }">{{ actionError }}</div>

		<form v-if="creating && canManage" class="cp-card mail-form" @submit.prevent="createCampaign">
			<h3>Новая рассылка</h3>
			<label>Название<input v-model.trim="form.name" required maxlength="180"></label>
			<label>Тема письма<input v-model.trim="form.subject" required maxlength="255"></label>
			<label>Текст<textarea v-model="form.body" required rows="8"></textarea></label>
			<div class="mail-segment">
				<label><input v-model="form.verified_only" type="checkbox"> Только подтверждённые email</label>
				<label><input v-model="form.active" type="checkbox"> Только активные аккаунты</label>
			</div>
			<label>Роли через запятую<input v-model.trim="form.roles" placeholder="user, manager"></label>
			<label>Коды тарифов через запятую<input v-model.trim="form.tariff_codes" placeholder="demo, pro"></label>
			<div class="cp-actions"><BaseButton type="submit" variant="primary" text="Сохранить черновик" /><BaseButton variant="outline" text="Отмена" @click="creating = false" /></div>
		</form>

		<div class="mail-toolbar">
			<label>Статус кампании
				<select v-model="campaignStatus" @change="applyCampaignFilter">
					<option value="">Все</option><option value="draft">Черновики</option><option value="scheduled">Запланированные</option><option value="queued">В очереди</option><option value="sending">Отправляются</option><option value="completed">Завершённые</option><option value="failed">С ошибками</option><option value="cancelled">Отменённые</option>
				</select>
			</label>
		</div>

		<div v-if="loading" class="cp-state">Загружаем рассылки…</div>
		<div v-else-if="error" class="cp-state cp-state--error">{{ error }}</div>
		<div v-else class="mail-layout">
			<div class="cp-card mail-list">
				<div class="mail-list__head"><h3>Кампании</h3><span class="cp-chip">{{ campaignTotal }}</span></div>
				<div v-if="campaigns.length === 0" class="cp-state">Рассылок пока нет.</div>
				<button v-for="campaign in campaigns" :key="campaign.id" type="button" class="campaign-row" :class="{ active: selected?.id === campaign.id }" @click="openCampaign(campaign)">
					<div><strong>{{ campaign.name }}</strong><span>{{ campaign.subject }}</span><small v-if="campaign.scheduled_at">Старт: {{ formatDate(campaign.scheduled_at) }}</small></div>
					<div class="campaign-row__meta"><span class="cp-chip">{{ statusLabel(campaign.status) }}</span><small>{{ campaign.sent_count }}/{{ campaign.audience_count }}</small></div>
				</button>
				<div v-if="campaignTotal > campaignLimit" class="mail-pagination"><BaseButton variant="outline" text="Назад" :disabled="campaignOffset === 0" @click="campaignPageDelta(-1)" /><span>{{ campaignPage }} / {{ campaignPages }}</span><BaseButton variant="outline" text="Далее" :disabled="campaignOffset + campaignLimit >= campaignTotal" @click="campaignPageDelta(1)" /></div>
			</div>

			<div v-if="selected" class="cp-card mail-detail">
				<div class="mail-detail__head"><div><p class="cp-eyebrow">Кампания</p><h3>{{ selected.name }}</h3><p class="cp-card-note">{{ selected.subject }}</p><p v-if="selected.scheduled_at" class="cp-card-note">Запланирована на {{ formatDate(selected.scheduled_at) }}</p></div><span class="cp-chip">{{ statusLabel(selected.status) }}</span></div>
				<div class="mail-stats"><div><span>Аудитория</span><strong>{{ selected.audience_count }}</strong></div><div><span>Отправлено</span><strong>{{ selected.sent_count }}</strong></div><div><span>Ошибки</span><strong>{{ selected.failed_count }}</strong></div><div><span>Подавлено</span><strong>{{ selected.suppressed_count }}</strong></div></div>
				<pre class="mail-body">{{ selected.body }}</pre>
				<div v-if="canManage && ['draft','scheduled'].includes(selected.status)" class="cp-actions mail-launch-actions">
					<BaseButton variant="outline" text="Рассчитать аудиторию" @click="previewCampaign" />
					<BaseButton variant="primary" text="Запустить сейчас" @click="requestConfirmation('launch')" />
				</div>
				<div v-if="canManage && ['draft','scheduled'].includes(selected.status)" class="mail-schedule">
					<label>Запланировать запуск<input v-model="scheduleAt" type="datetime-local" :min="minScheduleAt"></label>
					<BaseButton variant="outline" text="Запланировать" :disabled="!scheduleAt" @click="scheduleCampaign" />
				</div>
				<div v-if="canManage && !['draft','completed','cancelled','failed'].includes(selected.status)" class="cp-actions"><BaseButton variant="outline" text="Остановить" @click="requestConfirmation('cancel')" /></div>
				<div v-if="canManage" class="mail-test"><input v-model.trim="testEmail" type="email" placeholder="Email для теста"><BaseButton variant="outline" text="Тестовое письмо" :disabled="!testEmail" @click="sendTest" /></div>
				<div v-if="preview" class="mail-preview"><strong>{{ preview.deliverable_count }}</strong> получателей после suppression <span>({{ preview.suppressed_count }} исключено)</span></div>

				<div class="mail-delivery-head"><h4>Доставка</h4><select v-model="messageStatus" @change="applyMessageFilter"><option value="">Все статусы</option><option value="queued">В очереди</option><option value="sending">Отправляется</option><option value="sent">Отправлено</option><option value="failed">Ошибка</option><option value="suppressed">Подавлено</option><option value="cancelled">Отменено</option></select></div>
				<div v-if="messages.length === 0" class="cp-state">Сообщений ещё нет.</div>
				<div v-else class="cp-table-scroll"><table class="cp-table"><thead><tr><th>Email</th><th>Статус</th><th>Попытки</th><th>Ошибка</th><th>Отправлено</th></tr></thead><tbody><tr v-for="item in messages" :key="item.id"><td>{{ item.recipient_email }}</td><td>{{ item.status }}</td><td>{{ item.attempt_count }}/{{ item.max_attempts }}</td><td>{{ item.safe_error_code || '—' }}</td><td>{{ formatDate(item.sent_at) }}</td></tr></tbody></table></div>
				<div v-if="messageTotal > messageLimit" class="mail-pagination"><BaseButton variant="outline" text="Назад" :disabled="messageOffset === 0" @click="messagePageDelta(-1)" /><span>{{ messagePage }} / {{ messagePages }} · {{ messageTotal }}</span><BaseButton variant="outline" text="Далее" :disabled="messageOffset + messageLimit >= messageTotal" @click="messagePageDelta(1)" /></div>
			</div>
			<div v-else class="cp-state">Выберите рассылку слева.</div>
		</div>

		<Modal :is-open="Boolean(confirmAction)" size="small" :close-on-overlay-click="true" @close="confirmAction = null">
			<template #header><div class="mail-confirm__header"><h3>{{ confirmTitle }}</h3></div></template>
			<template #body><p class="mail-confirm__text">{{ confirmText }}</p></template>
			<template #footer><div class="cp-actions"><BaseButton variant="outline" text="Отмена" @click="confirmAction = null" /><BaseButton variant="primary" :text="confirmAction === 'cancel' ? 'Остановить' : 'Запустить'" @click="confirmPendingAction" /></div></template>
		</Modal>
	</section>
</template>

<style scoped>
.mail-header { display: flex; align-items: flex-end; justify-content: space-between; gap: 20px; }
.mail-toolbar { display: flex; justify-content: flex-end; margin-bottom: 12px; }
.mail-toolbar label, .mail-schedule label { display: grid; gap: 6px; color: #9fb0c8; font-size: 12px; }
.mail-toolbar select, .mail-delivery-head select, .mail-schedule input { border: 1px solid #334158; border-radius: 8px; background: #0e1520; color: #fff; padding: 9px 11px; }
.mail-layout { display: grid; grid-template-columns: minmax(280px, .7fr) minmax(0, 1.3fr); gap: 18px; }
.mail-list, .mail-detail, .mail-form { padding: 18px; }
.mail-list__head, .mail-detail__head, .mail-delivery-head { display: flex; justify-content: space-between; gap: 14px; align-items: flex-start; }
.campaign-row { width: 100%; display: flex; justify-content: space-between; gap: 12px; text-align: left; color: inherit; background: transparent; border: 0; border-top: 1px solid #263348; padding: 14px 4px; cursor: pointer; }
.campaign-row.active { background: rgba(129, 73, 255, .08); }
.campaign-row div:first-child { display: grid; gap: 4px; }
.campaign-row span, .campaign-row small { color: #9fb0c8; }
.campaign-row__meta { display: grid; justify-items: end; gap: 6px; }
.mail-form { display: grid; gap: 14px; margin-bottom: 18px; }
.mail-form label { display: grid; gap: 7px; color: #b9c6d8; }
.mail-form input, .mail-form textarea, .mail-test input { border: 1px solid #334158; border-radius: 8px; background: #0e1520; color: #fff; padding: 10px 12px; }
.mail-segment { display: flex; flex-wrap: wrap; gap: 20px; }
.mail-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin: 18px 0; }
.mail-stats div { padding: 12px; border-radius: 10px; background: #101824; display: grid; gap: 4px; }
.mail-stats span { color: #8fa2bc; font-size: 12px; }
.mail-stats strong { font-size: 22px; }
.mail-body { white-space: pre-wrap; font: inherit; line-height: 1.55; background: #0d141f; border: 1px solid #263348; border-radius: 10px; padding: 14px; max-height: 260px; overflow: auto; }
.mail-test, .mail-schedule { display: flex; gap: 10px; margin: 14px 0 20px; align-items: end; }
.mail-test input, .mail-schedule label { flex: 1; }
.mail-preview { margin: 12px 0 20px; padding: 12px; border-radius: 9px; background: rgba(129,73,255,.09); }
.mail-pagination { display: flex; align-items: center; justify-content: center; gap: 10px; margin-top: 14px; color: #9fb0c8; }
.mail-delivery-head { align-items: center; margin-top: 18px; }
.mail-confirm__header h3 { margin: 0 0 10px; }
.mail-confirm__text { margin: 0; color: #b9c6d8; line-height: 1.5; }
@media (max-width: 900px) { .mail-layout { grid-template-columns: 1fr; } .mail-stats { grid-template-columns: repeat(2, 1fr); } .mail-header { align-items: flex-start; flex-direction: column; } .mail-schedule { align-items: stretch; flex-direction: column; } }
</style>
