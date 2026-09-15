<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from './stores/auth'
import AuthService from './API/AuthService.js'
import LoginModal from './components/CustomModals/AuthModals/LoginModal.vue'
import RegistrationModal from './components/CustomModals/AuthModals/RegistrationModal.vue'
import DashboardAccountSelect from './components/DashboardAccountSelect.vue'
import { useDashboardAccount } from './composables/dashboardAccount.js'

const authStore = useAuthStore()
const router = useRouter()
const route = useRoute()
const { selectedTokenId, dashboardVersion } = useDashboardAccount()

const navItems = [
  { name: 'dashboard.home', label: 'Обзор' },
  { name: 'dashboard.unity', label: 'Юнит-экономика' },
  { name: 'dashboard.finance', label: 'Финансы' },
  { name: 'dashboard.stocks', label: 'Остатки' },
  { name: 'dashboard.prices', label: 'Цены' },
  { name: 'dashboard.ads', label: 'Реклама' },
]

const isAuthenticated = computed(() => authStore.isAuthSatus)
const user = computed(() => authStore.getUser)
const isControlPanelRoute = computed(() => route.path.startsWith('/control-panel'))
const showAccountFilter = computed(() => navItems.some(item => item.name === route.name))
const dashboardViewKey = computed(() => `${route.fullPath}:${selectedTokenId.value || 'all'}:${dashboardVersion.value}`)
const isAdmin = computed(() => user.value?.roles?.some(role => role === 'super_admin' || role === 'admin'))
const currentYear = new Date().getFullYear()

const showLogin = ref(false)
const showRegister = ref(false)

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
  <header class="app-header">
    <div class="app-header__inner">
      <RouterLink to="/" class="brand" aria-label="WB Insight — на главную">
        <span class="brand__mark">WB</span>
        <span class="brand__name">Insight</span>
        <span class="brand__badge">AI</span>
      </RouterLink>

      <div class="header-actions">
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
            <div class="menu-divider" />
            <button class="menu-action menu-action--danger" type="button" @click="logout">
              Выйти
            </button>
          </div>
        </details>

        <div v-else class="auth-actions">
          <button class="button button--ghost" type="button" @click="showLogin = true">Войти</button>
          <button class="button button--primary" type="button" @click="showRegister = true">Регистрация</button>
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

  <footer v-if="!isAuthenticated" class="app-footer">
    © {{ currentYear }} WB Insight
  </footer>
</template>

<style scoped>
.app-header {
  position: sticky;
  top: 0;
  z-index: 50;
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
  background: rgba(15, 20, 28, 0.9);
  backdrop-filter: blur(16px);
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
  background: linear-gradient(135deg, #7c3aed, #9333ea);
  color: #fff;
  font-size: 13px;
  letter-spacing: 0.02em;
}

.brand__name {
  font-size: 18px;
}

.brand__badge {
  padding: 2px 6px;
  border: 1px solid rgba(167, 139, 250, 0.3);
  border-radius: 6px;
  color: #c4b5fd;
  font-size: 10px;
  font-weight: 700;
}

.header-actions,
.auth-actions {
  display: flex;
  align-items: center;
  gap: 8px;
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
  background: #263449;
  color: #c4b5fd;
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
  color: #fda4af;
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
  background: rgba(24, 33, 46, 0.82);
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
  color: #fff;
  background: rgba(124, 58, 237, 0.22);
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