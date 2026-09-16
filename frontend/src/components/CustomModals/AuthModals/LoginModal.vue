<template>
	<Modal :is-open="isOpen" @close="$emit('close')">
		<template #header>
			<div class="modal-header">
				<h3 class="modal-title">Авторизация</h3>
				<button class="modal-close" @click="$emit('close')">&times;</button>
			</div>
		</template>

		<template #body>
			<div class="modal-body">
				<TextInput v-model="loginEmail" label="Email" placeholder="Введите email" type="email" />
				<TextInput v-model="loginPassword" label="Пароль" placeholder="Введите пароль" type="password" />
				<div class="auth-links">
					<button class="recovery-link" type="button" @click="openRecovery">Забыли пароль?</button>
					<button v-if="needsVerification" class="recovery-link" type="button" @click="openVerification">Подтвердить email</button>
				</div>
			</div>
			<div class="modal-error" v-if="loginError !== ''">{{ loginError }}</div>
		</template>

		<template #footer>
			<div class="modal-footer">
				<ButtonCancel @click="$emit('close')" />
				<ButtonLogin @click="performLogin" :loading="modalLoadedBtn" :disabled="modalLoadedBtn" />
			</div>
		</template>
	</Modal>
</template>
<script setup>
import { ref } from 'vue'
import Modal from '@/components/UI/Modal.vue'
import TextInput from '@/components/UI/TextInput.vue'
import ButtonLogin from '@/components/UI/Buttons/ButtonLogin.vue'
import ButtonCancel from '@/components/UI/Buttons/ButtonCancel.vue'
import AuthService from '@/API/AuthService';
import { useAuthStore } from '@/stores/auth';
import { useRouter } from 'vue-router';

const authStore = useAuthStore();
const router = useRouter();
const props = defineProps({ isOpen: Boolean });
const emit = defineEmits(['close'])

const loginEmail = ref('')
const loginPassword = ref('')
const loginError = ref('')
const modalLoadedBtn = ref(false)
const needsVerification = ref(false)

const openRecovery = async () => {
	emit('close')
	await router.push('/reset-password')
}

const openVerification = async () => {
	sessionStorage.setItem('pendingVerificationEmail', loginEmail.value.trim())
	emit('close')
	await router.push('/verify-email')
}

const performLogin = async () => {
	modalLoadedBtn.value = true
	needsVerification.value = false
	if (loginEmail.value === '' && loginPassword.value === '') {
		modalLoadedBtn.value = false
		loginError.value = 'Введите email и пароль'
		return
	}

	try {
		const response = await AuthService.login(loginEmail.value, loginPassword.value)
		if (response.data?.access_token && response.data?.user) {
			authStore.login(response.data)
			const redirectPath = localStorage.getItem('redirectPath')
			localStorage.removeItem('redirectPath')
			await router.push(redirectPath || '/dashboard')
			emit('close')
		}
	} catch (error) {
		console.error(error)
		if (error.response) {
			const code = error.response.data?.error?.code
			needsVerification.value = code === 'EMAIL_NOT_VERIFIED'
			loginError.value = error.response.data?.error?.message || error.response.data?.message || 'Ошибка авторизации'
		}
	} finally {
		modalLoadedBtn.value = false
	}
}
</script>
<style scoped>
.modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.modal-title { font-size: 20px; font-weight: 600; }
.modal-close { background: none; border: none; font-size: 24px; cursor: pointer; color: #aaa; }
.modal-body { margin-bottom: 20px; }
.auth-links { display: flex; justify-content: space-between; gap: 14px; flex-wrap: wrap; margin-top: 10px; }
.recovery-link { padding: 0; border: 0; background: transparent; color: inherit; text-decoration: underline; cursor: pointer; opacity: .78; }
.modal-footer { display: flex; justify-content: flex-end; gap: 10px; }
</style>