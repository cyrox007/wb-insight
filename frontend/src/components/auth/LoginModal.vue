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
				<div class="form-group">
					<label class="form-label">Email</label>
					<input type="email" class="form-input" v-model="loginEmail" placeholder="Введите email">
				</div>
				<div class="form-group">
					<label class="form-label">Пароль</label>
					<input type="password" class="form-input" v-model="loginPassword" placeholder="Введите пароль">
				</div>
			</div>
			<div class="modal-error" v-if="loginError !== ''">{{ loginError }}</div>
		</template>

		<template #footer>
			<div class="modal-footer">
				<button class="btn btn-outline" @click="$emit('close')">Отмена</button>
				<button class="btn btn-primary" @click="performLogin" :disabled="modalLoadedBtn">
					<SpinnerButtonSmall v-if="modalLoadedBtn" />
					<span>Войти</span>
				</button>
			</div>
		</template>
	</Modal>
</template>
<script setup>
import { ref, defineProps, defineEmits } from 'vue'
import Modal from '@/components/UI/Modal.vue'
import SpinnerButtonSmall from '@/components/Loaders/SpinnerButtonSmall.vue'
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

.form-group {
	margin-bottom: 15px;
}

.form-label {
	display: block;
	margin-bottom: 5px;
	font-size: 14px;
}

.form-input {
	width: 100%;
	padding: 10px;
	border: 1px solid var(--border-color);
	border-radius: 6px;
	background-color: var(--medium-bg);
	color: var(--text-color);
}

.form-input:focus {
	outline: none;
	border-color: var(--secondary-color);
}

.modal-footer {
	display: flex;
	justify-content: flex-end;
	gap: 10px;
}

.btn {
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
}
</style>