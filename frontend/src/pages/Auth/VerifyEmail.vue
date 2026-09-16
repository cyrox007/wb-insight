<script setup>
import { computed, onMounted, ref } from 'vue'
import AuthService from '@/API/AuthService'
import BaseButton from '@/components/UI/Buttons/BaseButton.vue'

const state = ref('pending')
const message = ref('Проверьте почту и откройте ссылку подтверждения.')
const resendBusy = ref(false)
const pendingEmail = ref(sessionStorage.getItem('pendingVerificationEmail') || '')

const title = computed(() => ({
	pending: 'Подтверждение email',
	checking: 'Проверяем ссылку…',
	success: 'Email подтверждён',
	error: 'Не удалось подтвердить email',
}[state.value] || 'Подтверждение email'))

function tokenFromHash() {
	const raw = window.location.hash.replace(/^#/, '')
	const params = new URLSearchParams(raw)
	return params.get('token') || ''
}

async function confirmFromHash() {
	const token = tokenFromHash()
	if (!token) return
	state.value = 'checking'
	message.value = 'Проверяем одноразовую ссылку…'
	try {
		const { data } = await AuthService.confirmEmail(token)
		if (data?.status !== 'success') throw new Error(data?.error?.message || 'Ссылка недействительна')
		state.value = 'success'
		message.value = data.message || 'Адрес подтверждён. Теперь можно войти в WB Insight.'
		sessionStorage.removeItem('pendingVerificationEmail')
	} catch (error) {
		state.value = 'error'
		message.value = error.response?.data?.error?.message || error.message || 'Ссылка недействительна или истекла.'
	} finally {
		history.replaceState(null, '', `${window.location.pathname}${window.location.search}`)
	}
}

async function resend() {
	if (!pendingEmail.value || resendBusy.value) return
	resendBusy.value = true
	try {
		const { data } = await AuthService.resendEmailVerification(pendingEmail.value)
		message.value = data?.message || 'Если адрес ожидает подтверждения, новое письмо будет отправлено.'
		state.value = 'pending'
	} catch (error) {
		message.value = error.response?.data?.error?.message || 'Не удалось запросить новое письмо.'
		state.value = 'error'
	} finally {
		resendBusy.value = false
	}
}

onMounted(confirmFromHash)
</script>

<template>
	<main class="verify-shell">
		<section class="verify-card" aria-live="polite">
			<p class="verify-eyebrow">WB Insight · безопасность аккаунта</p>
			<h1>{{ title }}</h1>
			<p class="verify-message">{{ message }}</p>

			<div v-if="state === 'pending' || state === 'error'" class="verify-resend">
				<label for="verification-email">Email</label>
				<input id="verification-email" v-model.trim="pendingEmail" type="email" autocomplete="email" placeholder="you@example.com">
				<BaseButton variant="outline" text="Отправить письмо ещё раз" :loading="resendBusy" :disabled="!pendingEmail" @click="resend" />
			</div>

			<div class="verify-actions">
				<router-link to="/" class="verify-link">Вернуться на главную</router-link>
			</div>
		</section>
	</main>
</template>

<style scoped>
.verify-shell {
	min-height: calc(100vh - 64px);
	display: grid;
	place-items: center;
	padding: 32px 16px;
	background: #0d131d;
	color: #f4f7fb;
}
.verify-card {
	width: min(520px, 100%);
	padding: 28px;
	border: 1px solid #2a3547;
	border-radius: 16px;
	background: #151d29;
	box-shadow: 0 18px 50px rgba(0,0,0,.22);
}
.verify-eyebrow { margin: 0 0 8px; color: #a77bff; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: .08em; }
h1 { margin: 0 0 12px; font-size: 30px; }
.verify-message { margin: 0; color: #b7c4d8; line-height: 1.55; }
.verify-resend { display: grid; gap: 10px; margin-top: 24px; }
.verify-resend label { font-size: 13px; color: #c8d3e3; }
.verify-resend input { width: 100%; box-sizing: border-box; padding: 11px 12px; border: 1px solid #334158; border-radius: 9px; background: #0e1520; color: #fff; }
.verify-actions { margin-top: 22px; }
.verify-link { color: #a77bff; text-decoration: none; }
.verify-link:hover { text-decoration: underline; }
</style>
