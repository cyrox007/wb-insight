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
import { ref, defineProps, defineEmits } from 'vue'
import Modal from '@/components/UI/Modal.vue'
import TextInput from '@/components/UI/TextInput.vue'
/* import SpinnerButtonSmall from '@/components/Loaders/SpinnerButtonSmall.vue' */
import ButtonLogin from '@/components/UI/Buttons/ButtonLogin.vue'
import ButtonCancel from '@/components/UI/Buttons/ButtonCancel.vue'
import AuthService from '@/API/AuthService';
import { useAuthStore } from '@/stores/auth';
import { useRouter } from 'vue-router';

const authStore = useAuthStore();
const router = useRouter();

const props = defineProps({
	isOpen: Boolean
});

const emit = defineEmits(['close'])

const loginEmail = ref('')
const loginPassword = ref('')
const loginError = ref('')
const modalLoadedBtn = ref(false)

const performLogin = async () => {
	// Логика входа
	modalLoadedBtn.value = true;
	if (loginEmail.value === '' && loginPassword.value === '') {
		modalLoadedBtn.value = false
		loginError.value = 'Введите email и пароль'
		return;
	}

	try {
		let response = await AuthService.login(loginEmail.value, loginPassword.value);
		if (response.data && response.data.data) {
			if (response.data.data.access_token) {
				authStore.login(response.data.data.user);
				localStorage.setItem("access_token", response.data.data.access_token);
				localStorage.setItem("user", JSON.stringify(response.data.data.user));
				router.push('/dashboard');
				emit('close')
			}
		}

	} catch (error) {
		console.error(error);
		if (error.response) {
			loginError.value = error.response.data.message || 'Ошибка авторизации';
		}
	} finally {
		modalLoadedBtn.value = false
	}
}
</script>
<style scoped>
.modal-header {
	display: flex;
	justify-content: space-between;
	align-items: center;
	margin-bottom: 20px;
}

.modal-title {
	font-size: 20px;
	font-weight: 600;
}

.modal-close {
	background: none;
	border: none;
	font-size: 24px;
	cursor: pointer;
	color: #aaa;
}

.modal-body {
	margin-bottom: 20px;
}

.modal-footer {
	display: flex;
	justify-content: flex-end;
	gap: 10px;
}

/* .btn {
	padding: 10px 20px;
	border-radius: 6px;
	border: none;
	cursor: pointer;
	font-size: 14px;
	font-weight: 500;
	transition: all 0.2s;
	display: flex;
	align-items: center;
	gap: 8px;
}

.btn-outline {
	background-color: transparent;
	border: 1px solid var(--border-color);
	color: var(--text-color);
}

.btn-outline:hover {
	background-color: var(--hover-bg);
}

.btn-primary {
	background-color: var(--secondary-color);
	color: white;
}

.btn-primary:hover:not(:disabled) {
	background-color: #2980b9;
}

.btn-primary:disabled {
	opacity: 0.6;
	cursor: not-allowed;
} */
</style>