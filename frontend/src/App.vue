<script setup>
import { ref, computed } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useAuthStore } from './stores/auth';
import LoginModal from './components/CustomModals/AuthModals/LoginModal.vue';
import RegistrationModal from './components/CustomModals/AuthModals/RegistrationModal.vue';

// Реактивные переменные
const showHeader = ref(true)
const showFooter = ref(true)

const authStore = useAuthStore();
const router = useRouter();
const route = useRoute();

const navItems = [
	{ name: 'dashboard.home', label: 'Ключевые показатели' },
	{ name: 'unit', label: 'Unit-экономика' },
	{ name: 'ads', label: 'Внутренняя реклама' },
	{ name: 'rnp', label: 'РнП' },
	{ name: 'month', label: 'Показатели месяца' },
	{ name: 'jam', label: 'РнП (Джем)' },
	{ name: 'cost', label: 'С/С' }
]

const isActive = (name) => route.name === name

// Авторизация
const isAuthenticated = computed(() => authStore.isAuthSatus);
const user = computed(() => authStore.getUser);
const isControlPanelRoute = computed(() => route.path.startsWith('/control-panel'));
const isAdmin = computed(() => {
	return user.value.roles?.some(
		role => role === 'super_admin' || role === 'administrator'
	)
})

// Модальные окна
const showLogin = ref(false)
const showRegister = ref(false)

const logout = () => {
	localStorage.clear();
	router.push('/');
	authStore.logout()
}

</script>

<template>
	<header class="header" v-if="showHeader">
		<div class="header-left">
			<div class="logo">WB<span>Insight</span>
				&lt;&lt; AI &gt;&gt; </div>
		</div>
		<div class="header-right">
			<!-- Блок пользователя/авторизации -->
			<div class="user-section" v-if="isAuthenticated">
				<div class="dropdown user-dropdown">
					<div class="user-menu">
						{{ user.full_name }}
					</div>
					<div class="dropdown-content">
						<div v-show="isAdmin" @click="router.push({ name: 'control-panel.index' })"
							class="dropdown-item">
							Панель управления
						</div>
						<div class="dropdown-item" @click="$router.push({ name: 'dashboard.profile' })">Профиль
						</div>

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
	<LoginModal :is-open="showLogin" @close="showLogin = false" />

	<!-- Модальное окно регистрации -->
	<RegistrationModal :is-open="showRegister" @close="showRegister = false" />

	<!-- Основной контент страниц -->
	<main class="main-content">
		<nav v-if="isAuthenticated && !isControlPanelRoute">
			<div v-for="item in navItems" :key="item.name" class="nav-item" :class="{ active: isActive(item.name) }"
				@click="router.push({ name: item.name })">
				{{ item.label }}
			</div>
		</nav>
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

.header-right {
	display: flex;
	align-items: center;
	gap: 15px;
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

nav {
	padding: 12px;
	margin: 20px;
	border-radius: 10px;
	background-color: var(--medium-bg);
	display: flex;
	gap: 10px;
	justify-content: center;
	flex-wrap: wrap;
	border: 1px solid var(--border-color);
}

.nav-item {
	padding: 8px 14px;
	border-radius: 6px;
	cursor: pointer;
	font-size: 14px;
	color: #ccc;
	transition: var(--transition);
	background-color: transparent;
	border: 1px solid transparent;
}

/* hover */
.nav-item:hover {
	background-color: var(--hover-bg);
	color: #fff;
	border-color: var(--border-color);
}

/* ACTIVE STATE 🔥 */
.nav-item.active {
	background-color: var(--secondary-color);
	color: white;
	border-color: var(--secondary-color);
	box-shadow: 0 2px 8px rgba(52, 152, 219, 0.3);
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
