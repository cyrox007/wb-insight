<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import CP_Mail from '@/API/ControlPanel/CP_Mail'
import BaseButton from '@/components/UI/Buttons/BaseButton.vue'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const campaigns = ref([])
const selected = ref(null)
const messages = ref([])
const loading = ref(false)
const error = ref('')
const actionError = ref('')
const creating = ref(false)
const preview = ref(null)
const testEmail = ref('')

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
const statusLabel = (value) => ({
	draft: 'Черновик', queued: 'В очереди', sending: 'Отправляется', completed: 'Завершена', failed: 'С ошибками', cancelled: 'Отменена',
}[value] || value)

async function loadCampaigns() {
	loading.value = true
	error.value = ''
	try {
		const { data } = await CP_Mail.getCampaigns()
		if (data?.status !== 'success' || !Array.isArray(data?.campaigns)) throw new Error('Некорректный ответ API')
		campaigns.value = data.campaigns
		if (selected.value) {
			selected.value = campaigns.value.find((item) => item.id === selected.value.id) || selected.value
		}
	} catch (e) {
		error.value = e.response?.data?.error?.message || 'Не удалось загрузить рассылки.'
	} finally {
		loading.value = false
	}
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
		await loadCampaigns()
		await openCampaign(data.campaign)
	} catch (e) {
		actionError.value = e.response?.data?.error?.message || e.message || 'Не удалось создать кампанию.'
	}
}

async function openCampaign(campaign) {
	selected.value = campaign
	preview.value = null
	messages.value = []
	try {
		const [{ data: detail }, { data: delivery }] = await Promise.all([
			CP_Mail.getCampaign(campaign.id),
			CP_Mail.getMessages(campaign.id),
		])
		if (detail?.campaign) selected.value = detail.campaign
		messages.value = delivery?.messages || []
	} catch (e) {
		actionError.value = e.response?.data?.error?.message || 'Не удалось открыть рассылку.'
	}
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

async function launchCampaign() {
	if (!selected.value || !confirm('Запустить рассылку на рассчитанную аудиторию?')) return
	actionError.value = ''
	try {
		const { data } = await CP_Mail.launch(selected.value.id)
		if (data?.campaign) selected.value = data.campaign
		await loadCampaigns()
		await openCampaign(selected.value)
	} catch (e) {
		actionError.value = e.response?.data?.error?.message || 'Не удалось запустить рассылку.'
	}
}

async function cancelCampaign() {
	if (!selected.value || !confirm('Остановить неотправленные письма этой кампании?')) return
	try {
		const { data } = await CP_Mail.cancel(selected.value.id)
		if (data?.campaign) selected.value = data.campaign
		await loadCampaigns()
		await openCampaign(selected.value)
	} catch (e) {
		actionError.value = e.response?.data?.error?.message || 'Не удалось остановить рассылку.'
	}
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

		<div v-if="loading" class="cp-state">Загружаем рассылки…</div>
		<div v-else-if="error" class="cp-state cp-state--error">{{ error }}</div>
		<div v-else class="mail-layout">
			<div class="cp-card mail-list">
				<div class="mail-list__head"><h3>Кампании</h3><span class="cp-chip">{{ campaigns.length }}</span></div>
				<div v-if="campaigns.length === 0" class="cp-state">Рассылок пока нет.</div>
				<button v-for="campaign in campaigns" :key="campaign.id" type="button" class="campaign-row" :class="{ active: selected?.id === campaign.id }" @click="openCampaign(campaign)">
					<div><strong>{{ campaign.name }}</strong><span>{{ campaign.subject }}</span></div>
					<div class="campaign-row__meta"><span class="cp-chip">{{ statusLabel(campaign.status) }}</span><small>{{ campaign.sent_count }}/{{ campaign.audience_count }}</small></div>
				</button>
			</div>

			<div v-if="selected" class="cp-card mail-detail">
				<div class="mail-detail__head"><div><p class="cp-eyebrow">Кампания</p><h3>{{ selected.name }}</h3><p class="cp-card-note">{{ selected.subject }}</p></div><span class="cp-chip">{{ statusLabel(selected.status) }}</span></div>
				<div class="mail-stats"><div><span>Аудитория</span><strong>{{ selected.audience_count }}</strong></div><div><span>Отправлено</span><strong>{{ selected.sent_count }}</strong></div><div><span>Ошибки</span><strong>{{ selected.failed_count }}</strong></div><div><span>Подавлено</span><strong>{{ selected.suppressed_count }}</strong></div></div>
				<pre class="mail-body">{{ selected.body }}</pre>
				<div v-if="canManage && selected.status === 'draft'" class="cp-actions">
					<BaseButton variant="outline" text="Рассчитать аудиторию" @click="previewCampaign" />
					<BaseButton variant="primary" text="Запустить" @click="launchCampaign" />
				</div>
				<div v-if="canManage && !['draft','completed','cancelled'].includes(selected.status)" class="cp-actions"><BaseButton variant="outline" text="Остановить" @click="cancelCampaign" /></div>
				<div v-if="canManage" class="mail-test"><input v-model.trim="testEmail" type="email" placeholder="Email для теста"><BaseButton variant="outline" text="Тестовое письмо" :disabled="!testEmail" @click="sendTest" /></div>
				<div v-if="preview" class="mail-preview"><strong>{{ preview.deliverable_count }}</strong> получателей после suppression <span>({{ preview.suppressed_count }} исключено)</span></div>

				<h4>Доставка</h4>
				<div v-if="messages.length === 0" class="cp-state">Сообщений ещё нет.</div>
				<div v-else class="cp-table-scroll"><table class="cp-table"><thead><tr><th>Email</th><th>Статус</th><th>Попытки</th><th>Ошибка</th><th>Отправлено</th></tr></thead><tbody><tr v-for="item in messages" :key="item.id"><td>{{ item.recipient_email }}</td><td>{{ item.status }}</td><td>{{ item.attempt_count }}/{{ item.max_attempts }}</td><td>{{ item.safe_error_code || '—' }}</td><td>{{ item.sent_at ? new Date(item.sent_at).toLocaleString('ru-RU') : '—' }}</td></tr></tbody></table></div>
			</div>
			<div v-else class="cp-state">Выберите рассылку слева.</div>
		</div>
	</section>
</template>

<style scoped>
.mail-header { display: flex; align-items: flex-end; justify-content: space-between; gap: 20px; }
.mail-layout { display: grid; grid-template-columns: minmax(280px, .7fr) minmax(0, 1.3fr); gap: 18px; }
.mail-list, .mail-detail, .mail-form { padding: 18px; }
.mail-list__head, .mail-detail__head { display: flex; justify-content: space-between; gap: 14px; align-items: flex-start; }
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
.mail-test { display: flex; gap: 10px; margin: 14px 0 20px; }
.mail-test input { flex: 1; }
.mail-preview { margin: 12px 0 20px; padding: 12px; border-radius: 9px; background: rgba(129,73,255,.09); }
@media (max-width: 900px) { .mail-layout { grid-template-columns: 1fr; } .mail-stats { grid-template-columns: repeat(2, 1fr); } .mail-header { align-items: flex-start; flex-direction: column; } }
</style>
