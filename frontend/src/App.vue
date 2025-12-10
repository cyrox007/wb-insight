<script setup>
import { ref, onMounted, computed } from 'vue';
import { useRoute } from 'vue-router';
import { useAuthStore } from './stores/auth';
import AuthService from '../API/AuthService';
import SpinnerButtonSmall from './components/Loaders/SpinnerButtonSmall.vue';

// Реактивные переменные
const showHeader = ref(true)
const showFooter = ref(true)
const showSearch = ref(true)
const showDateRange = ref(true)

const modalLoadedBtn = ref(false)

// Авторизация
const authStore = useAuthStore();

const isAuthenticated = computed(() => authStore.isAuthSatus);
/*const userName = ref('Иван Иванов')
const userInitials = computed(() => {
	if (!userName.value) return ''
	return userName.value.split(' ').map(n => n[0]).join('').toUpperCase()
}) */

// Уведомления
const notificationCount = ref(3)
const showNotifications = ref(false)

// Модальные окна
const showLogin = ref(false)
const showRegister = ref(false)

// Данные форм
const loginEmail = ref('')
const loginPassword = ref('')
const loginError = ref('')

const registerName = ref('')
const registerEmail = ref('')
const registerPassword = ref('')

// Навигация
const searchQuery = ref('')
const startDate = ref('1 октября')
const endDate = ref('19 октября')

// Методы
const toggleNotifications = () => {
	showNotifications.value = !showNotifications.value
}

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
		console.log(response);

	} catch (error) {
		console.error(error);
		if (error.response) {
			loginError.value = error.response.data.message || 'Ошибка авторизации';
		}
	} finally {
		modalLoadedBtn.value = false
	}
}

const performRegister = () => {
	// Логика регистрации
	console.log('Register attempt:', registerEmail.value)
	isAuthenticated.value = true
	userName.value = registerName.value
	showRegister.value = false
}

const logout = () => {
	authStore.logout()
}

// Определяем, нужно ли показывать элементы на текущей странице
const route = useRoute()
onMounted(() => {
	// Можно настроить логику скрытия/показа элементов для разных страниц
	// Например, на странице входа не показывать хедер
})
</script>

<template>
	<header class="header" v-if="showHeader">
		<div class="header-left">
			<div class="logo">wild<span>berries</span></div>
			<div class="search-container" v-if="showSearch">
				<input type="text" class="search-input" placeholder="Выберите артикул..." v-model="searchQuery">
			</div>
			<div class="date-range" v-if="showDateRange">
				<span>Дата от</span>
				<input type="text" class="date-input" placeholder="1 октября" v-model="startDate">
				<span>до</span>
				<input type="text" class="date-input" placeholder="19 октября" v-model="endDate">
			</div>
		</div>
		<div class="header-right">
			<!-- Блок пользователя/авторизации -->
			<div class="user-section" v-if="isAuthenticated">
				<div class="notification-icon" @click="toggleNotifications">
					<i class="fas fa-bell"></i>
					<div class="notification-count" v-if="notificationCount > 0">{{ notificationCount }}</div>
				</div>
				<div class="dropdown user-dropdown">
					<button class="btn btn-outline">
						<div class="user-avatar-mini">{{ userInitials }}</div>
						{{ userName }}
					</button>
					<div class="dropdown-content">
						<div class="dropdown-item">Профиль</div>
						<div class="dropdown-item">Настройки</div>
						<div class="dropdown-divider"></div>
						<div class="dropdown-item" @click="logout">Выйти</div>
					</div>
				</div>
			</div>

			<!-- Блок авторизации для неавторизованных пользователей -->
			<div class="auth-section" v-else>
				<button class="btn btn-outline" @click="showLogin = true">

					<span>Войти</span>
				</button>
				<button class="btn btn-primary" @click="showRegister = true">Регистрация</button>
			</div>
		</div>
	</header>
	<!-- Модальное окно авторизации -->
	<div class="modal-overlay" v-if="showLogin">
		<div class="modal">
			<div class="modal-header">
				<h3 class="modal-title">Авторизация</h3>
				<button class="modal-close" @click="showLogin = false">&times;</button>
			</div>
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
			<div class="modal-footer">
				<button class="btn btn-outline" @click="showLogin = false">Отмена</button>
				<button class="btn btn-primary" @click="performLogin" :disabled="modalLoadedBtn">
					<SpinnerButtonSmall v-if="modalLoadedBtn" />
					Войти
				</button>
			</div>
		</div>
	</div>
	<!-- Основной контент страниц -->
	<main class="main-content">
		<RouterView />
	</main>

	<!-- Footer - общий для всех страниц -->
	<footer class="footer" v-if="showFooter">
		© 2025 Wildberries Dashboard. Все права защищены.
	</footer>
</template>

<style scoped>
/* Стили из вашего кода, которые относятся к общим элементам */
.header {
	background-color: var(--medium-bg);
	padding: 12px 20px;
	display: flex;
	justify-content: space-between;
	align-items: center;
	border-bottom: 1px solid var(--border-color);
	box-shadow: var(--shadow);
}

.header-left {
	display: flex;
	align-items: center;
	gap: 20px;
}

.logo {
	font-size: 24px;
	font-weight: bold;
	color: #fff;
	letter-spacing: 1px;
}

.logo span {
	color: #ff6b6b;
}

.search-container {
	display: flex;
	align-items: center;
	background-color: var(--light-bg);
	border-radius: 6px;
	padding: 8px 12px;
	width: 250px;
}

.search-input {
	flex: 1;
	background: transparent;
	border: none;
	color: var(--text-color);
	padding: 4px 8px;
	font-size: 14px;
}

.search-input:focus {
	outline: none;
}

.date-range {
	display: flex;
	align-items: center;
	gap: 10px;
	font-size: 14px;
}

.date-input {
	background-color: var(--light-bg);
	border: none;
	color: var(--text-color);
	padding: 6px 10px;
	border-radius: 4px;
	font-size: 14px;
}

.date-input:focus {
	outline: none;
}

.header-right {
	display: flex;
	align-items: center;
	gap: 15px;
}

.btn {
	padding: 8px 16px;
	border-radius: 6px;
	border: none;
	cursor: pointer;
	font-size: 14px;
	transition: var(--transition);
	display: flex;
	align-items: center;
	gap: 6px;
}

.btn-primary {
	background-color: var(--secondary-color);
	color: white;
}

.btn-primary:hover {
	background-color: #2980b9;
}

.btn-outline {
	background-color: transparent;
	border: 1px solid var(--border-color);
	color: var(--text-color);
}

.btn-outline:hover {
	background-color: var(--hover-bg);
}

.notification-icon {
	position: relative;
	cursor: pointer;
	padding: 8px;
	border-radius: 50%;
	background-color: var(--light-bg);
}

.notification-count {
	position: absolute;
	top: -6px;
	right: -6px;
	background-color: var(--accent-color);
	color: white;
	border-radius: 50%;
	width: 20px;
	height: 20px;
	display: flex;
	align-items: center;
	justify-content: center;
	font-size: 12px;
}

.dropdown {
	position: relative;
	display: inline-block;
}

.dropdown-content {
	display: none;
	position: absolute;
	background-color: var(--card-bg);
	min-width: 160px;
	box-shadow: var(--shadow);
	border-radius: 6px;
	z-index: 1;
	right: 0;
}

.dropdown:hover .dropdown-content {
	display: block;
}

.dropdown-item {
	padding: 10px 15px;
	cursor: pointer;
	transition: var(--transition);
}

.dropdown-item:hover {
	background-color: var(--hover-bg);
}

.dropdown-divider {
	height: 1px;
	background-color: var(--border-color);
	margin: 5px 0;
}

.user-section {
	display: flex;
	align-items: center;
	gap: 15px;
}

.user-avatar-mini {
	width: 30px;
	height: 30px;
	border-radius: 50%;
	background-color: var(--secondary-color);
	display: flex;
	align-items: center;
	justify-content: center;
	color: white;
	font-weight: bold;
	margin-right: 8px;
}

.auth-section {
	display: flex;
	gap: 10px;
}

.modal-overlay {
	position: fixed;
	top: 0;
	left: 0;
	right: 0;
	bottom: 0;
	background-color: rgba(0, 0, 0, 0.7);
	display: flex;
	align-items: center;
	justify-content: center;
	z-index: 1000;
}

.modal {
	background-color: var(--card-bg);
	border-radius: 8px;
	padding: 20px;
	width: 500px;
	max-width: 90%;
	box-shadow: var(--shadow);
}

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

.footer {
	background-color: var(--medium-bg);
	padding: 15px 20px;
	border-top: 1px solid var(--border-color);
	text-align: center;
	font-size: 14px;
	color: #aaa;
}

.main-content {
	min-height: calc(100vh - 120px);
	/* Высота экрана минус хедер и футер */
}
</style>
