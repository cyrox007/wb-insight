<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from './stores/auth'
import AuthService from './API/AuthService.js'
import LoginModal from './components/CustomModals/AuthModals/LoginModal.vue'
import RegistrationModal from './components/CustomModals/AuthModals/RegistrationModal.vue'
import DashboardAccountSelect from './components/DashboardAccountSelect.vue'
import { useDashboardAccount } from './composables/dashboardAccount.js'
import { useTheme } from './composables/theme.js'

const authStore = useAuthStore()
const router = useRouter()
const route = useRoute()
const { selectedTokenId, dashboardVersion } = useDashboardAccount()
const { isDark, toggleTheme } = useTheme()

const navItems = [
  { name: 'dashboard.home', label: 'Обзор' },
  { name: 'dashboard.unity', label: 'Юнит-экономика' },
  { name: 'dashboard.finance', label: 'Финансы' },
  { name: 'dashboard.stocks', label: 'Остатки' },
  { name: 'dashboard.prices', label: 'Цены' },
  { name: 'dashboard.ads', label: 'Реклама' },
]

const isAuthenticated = computed(() => authStore.isAuthSatus)
const isLandingGuest = computed(() => !isAuthenticated.value && route.name === 'home')
const user = computed(() => authStore.getUser)
const isControlPanelRoute = computed(() => route.path.startsWith('/control-panel'))
const showAccountFilter = computed(() => navItems.some(item => item.name === route.name))
const dashboardViewKey = computed(() => `${route.fullPath}:${selectedTokenId.value || 'all'}:${dashboardVersion.value}`)
const isAdmin = computed(() => user.value?.roles?.some(role => role === 'super_admin' || role === 'admin'))
const currentYear = new Date().getFullYear()

const showLogin = ref(false)
const showRegister = ref(false)

const openLogin = () => { showLogin.value = true }
const openRegister = () => { showRegister.value = true }

onMounted(() => {
  window.addEventListener('wb:open-login', openLogin)
  window.addEventListener('wb:open-register', openRegister)
})

onBeforeUnmount(() => {
  window.removeEventListener('wb:open-login', openLogin)
  window.removeEventListener('wb:open-register', openRegister)
})

const logout = async () => {
  try {
    await AuthService.logout()
  } catch (error) {
    console.warn('Не удалось завершить серверную сессию:', error)
  } finally {
    localStorage.removeItem('access_token')
    localStorage.removeItem('user')
    localStorage.removeItem('redirectPath')
    localStorage.removeItem('wb-dashboard-token-id')
    authStore.logout()
    await router.push('/')
  }
}
</script>

<template>
  <header class="app-header" :class="{ 'app-header--landing': isLandingGuest }">
    <div class="app-header__inner">
      <RouterLink to="/" class="brand" aria-label="WB Insight — на главную">
        <span class="brand__mark">WB</span>
        <span class="brand__name">Insight</span>
        <span class="brand__badge">AI</span>
      </RouterLink>

      <nav v-if="isLandingGuest" class="landing-header-nav" aria-label="Навигация промо-страницы">
        <a href="#features">Возможности</a>
        <a href="#how">Как работает</a>
        <a href="#roadmap">Roadmap</a>
        <a href="#faq">FAQ</a>
      </nav>

      <div class="header-actions">
        <button
          class="theme-toggle"
          type="button"
          :aria-label="isDark ? 'Включить светлую тему' : 'Включить тёмную тему'"
          :title="isDark ? 'Светлая тема' : 'Тёмная тема'"
          @click="toggleTheme"
        >
          <svg v-if="isDark" viewBox="0 0 24 24" aria-hidden="true">
            <circle cx="12" cy="12" r="4.25" />
            <path d="M12 2.5v2M12 19.5v2M4.6 4.6 6 6M18 18l1.4 1.4M2.5 12h2M19.5 12h2M4.6 19.4 6 18M18 6l1.4-1.4" />
          </svg>
          <svg v-else viewBox="0 0 24 24" aria-hidden="true">
            <path d="M20 15.4A8.3 8.3 0 0 1 8.6 4 8.5 8.5 0 1 0 20 15.4Z" />
          </svg>
        </button>

        <details v-if="isAuthenticated && user" class="user-menu">
          <summary class="user-menu__trigger" aria-label="Меню пользователя">
            <span class="avatar" aria-hidden="true">{{ user.full_name?.charAt(0) || user.email?.charAt(0) || 'U' }}</span>
            <span class="user-identity">
              <strong>{{ user.full_name || 'Пользователь' }}</strong>
              <small>{{ user.email }}</small>
            </span>
            <span class="chevron" aria-hidden="true">⌄</span>
          </summary>

          <div class="user-menu__content">
            <button v-if="isAdmin" class="menu-action" type="button" @click="router.push({ name: 'control-panel.index' })">
              Панель управления
            </button>
            <button class="menu-action" type="button" @click="router.push({ name: 'dashboard.profile' })">
              Профиль и подключения
            </button>
            <button class="menu-action" type="button" @click="router.push({ name: 'dashboard.account-security' })">
              Безопасность аккаунта
            </button>
            <div class="menu-divider" />
            <button class="menu-action menu-action--danger" type="button" @click="logout">
              Выйти
            </button>
          </div>
        </details>

        <div v-else class="auth-actions">
          <button class="button button--ghost" type="button" @click="openLogin">Войти</button>
          <button class="button button--primary" type="button" @click="openRegister">Регистрация</button>
        </div>
      </div>
    </div>
  </header>

  <LoginModal :is-open="showLogin" @close="showLogin = false" />
  <RegistrationModal :is-open="showRegister" @close="showRegister = false" />

  <main class="app-main">
    <section v-if="isAuthenticated && !isControlPanelRoute" class="workspace-bar" aria-label="Навигация аналитики">
      <nav class="workspace-nav">
        <RouterLink
          v-for="item in navItems"
          :key="item.name"
          :to="{ name: item.name }"
          class="workspace-nav__item"
          :class="{ 'workspace-nav__item--active': route.name === item.name }"
        >
          {{ item.label }}
        </RouterLink>
      </nav>
      <DashboardAccountSelect v-if="showAccountFilter" class="workspace-account" />
    </section>

    <RouterView :key="dashboardViewKey" />
  </main>

  <footer v-if="!isAuthenticated && !isLandingGuest" class="app-footer">
    © {{ currentYear }} WB Insight
  </footer>
</template>

<style scoped>
.app-header {
  position: sticky;
  top: 0;
  z-index: 50;
  border-bottom: 1px solid rgba(99, 91, 255, 0.1);
  background: var(--header-bg);
  backdrop-filter: blur(16px);
}

.app-header--landing {
  border-bottom-color: rgba(99, 91, 255, 0.1);
  background: var(--header-bg-soft);
  color: var(--text-color);
}

.app-header--landing .brand__name {
  color: var(--text-color);
}

.app-header--landing .brand__badge {
  color: var(--secondary-color);
  border-color: rgba(99, 91, 255, 0.22);
}

.app-header--landing .button--ghost {
  color: var(--text-color);
  border-color: var(--border-color);
}

.app-header--landing .button--ghost:hover {
  background: var(--hover-bg);
}

.landing-header-nav {
  display: flex;
  align-items: center;
  gap: 24px;
  margin-left: auto;
  margin-right: 24px;
  color: var(--text-muted);
  font-size: 13px;
  font-weight: 700;
}

.landing-header-nav a {
  transition: color var(--transition);
}

.landing-header-nav a:hover {
  color: var(--secondary-color);
}

.app-header__inner {
  width: min(100% - 32px, var(--content-width));
  min-height: 64px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
}

.brand {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-weight: 800;
  letter-spacing: -0.02em;
}

.brand__mark {
  display: inline-grid;
  place-items: center;
  min-width: 34px;
  height: 34px;
  padding: 0 7px;
  border-radius: 9px;
  background: linear-gradient(135deg, #635bff, #7a65e8);
  color: #fff;
  font-size: 13px;
  letter-spacing: 0.02em;
}

.brand__name {
  font-size: 18px;
}

.brand__badge {
  padding: 2px 6px;
  border: 1px solid rgba(99, 91, 255, 0.22);
  border-radius: 6px;
  color: var(--secondary-color);
  font-size: 10px;
  font-weight: 700;
}

.header-actions,
.auth-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.theme-toggle {
  width: 38px;
  height: 38px;
  display: inline-grid;
  place-items: center;
  flex: 0 0 auto;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  background: var(--medium-bg);
  color: var(--text-muted);
  box-shadow: var(--shadow-sm);
  cursor: pointer;
  transition: color var(--transition), border-color var(--transition), background var(--transition), transform var(--transition);
}

.theme-toggle:hover {
  color: var(--secondary-color);
  border-color: color-mix(in srgb, var(--secondary-color) 36%, var(--border-color));
  background: var(--hover-bg);
  transform: translateY(-1px);
}

.theme-toggle svg {
  width: 18px;
  height: 18px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.8;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.button {
  min-height: 38px;
  padding: 8px 14px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-color);
  background: transparent;
  cursor: pointer;
  transition: background var(--transition), border-color var(--transition), transform var(--transition);
}

.button:hover {
  background: var(--hover-bg);
}

.button--primary {
  border-color: var(--secondary-color);
  background: var(--secondary-color);
  color: #fff;
}

.button--primary:hover {
  background: var(--secondary-hover);
}

.user-menu {
  position: relative;
}

.user-menu summary {
  list-style: none;
}

.user-menu summary::-webkit-details-marker {
  display: none;
}

.user-menu__trigger {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 220px;
  padding: 6px 9px;
  border-radius: 10px;
  cursor: pointer;
  transition: background var(--transition);
}

.user-menu__trigger:hover,
.user-menu[open] .user-menu__trigger {
  background: var(--hover-bg);
}

.avatar {
  flex: 0 0 34px;
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border-radius: 9px;
  background: var(--hover-bg);
  color: var(--secondary-color);
  font-weight: 700;
}

.user-identity {
  min-width: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
}

.user-identity strong,
.user-identity small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-identity strong {
  font-size: 13px;
  font-weight: 650;
}

.user-identity small {
  margin-top: 1px;
  color: var(--text-muted);
  font-size: 11px;
}

.chevron {
  color: var(--text-muted);
}

.user-menu__content {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  min-width: 220px;
  padding: 6px;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  background: var(--card-bg-elevated);
  box-shadow: var(--shadow);
}

.menu-action {
  width: 100%;
  padding: 10px 11px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--text-color);
  text-align: left;
  cursor: pointer;
}

.menu-action:hover {
  background: var(--hover-bg);
}

.menu-action--danger {
  color: var(--danger-color);
}

.menu-divider {
  height: 1px;
  margin: 5px 4px;
  background: var(--border-color);
}

.app-main {
  min-height: calc(100vh - 64px);
}

.workspace-bar {
  width: min(100% - 32px, var(--content-width));
  margin: 18px auto 0;
  padding: 10px;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  background: var(--header-bg-soft);
  box-shadow: var(--shadow-sm);
}

.workspace-nav {
  display: flex;
  align-items: center;
  gap: 4px;
}

.workspace-nav__item {
  padding: 9px 13px;
  border-radius: 8px;
  color: var(--text-muted);
  font-size: 13px;
  font-weight: 600;
  transition: color var(--transition), background var(--transition);
}

.workspace-nav__item:hover {
  color: var(--text-color);
  background: var(--hover-bg);
}

.workspace-nav__item--active {
  color: var(--secondary-color);
  background: color-mix(in srgb, var(--secondary-color) 11%, transparent);
}

.workspace-account {
  margin-left: auto;
}

.app-footer {
  padding: 24px;
  color: var(--text-subtle);
  text-align: center;
  font-size: 12px;
}

@media (max-width: 900px) {
  .landing-header-nav {
    display: none;
  }

  .workspace-bar {
    align-items: stretch;
    flex-direction: column;
  }

  .workspace-account {
    width: 100%;
    margin-left: 0;
  }
}

@media (max-width: 640px) {
  .app-header__inner,
  .workspace-bar {
    width: min(100% - 20px, var(--content-width));
  }

  .brand__badge,
  .user-identity {
    display: none;
  }

  .user-menu__trigger {
    min-width: auto;
  }

  .workspace-nav {
    width: 100%;
    overflow-x: auto;
    scrollbar-width: none;
  }

  .workspace-nav::-webkit-scrollbar {
    display: none;
  }

  .workspace-nav__item {
    white-space: nowrap;
  }
}
</style>