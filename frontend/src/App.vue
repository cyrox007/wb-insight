<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from './stores/auth'
import AuthService from './API/AuthService.js'
import LoginModal from './components/CustomModals/AuthModals/LoginModal.vue'
import RegistrationModal from './components/CustomModals/AuthModals/RegistrationModal.vue'
import DashboardAccountSelect from './components/DashboardAccountSelect.vue'
import DashboardState from './components/DashboardState.vue'
import { useDashboardAccount } from './composables/dashboardAccount.js'
import { useTheme } from './composables/theme.js'
import { canAccessControlPanel, isStaffUser, ROLE_LABELS } from './security/roles.js'

const authStore = useAuthStore()
const router = useRouter()
const route = useRoute()
const {
  accounts,
  allWbAccounts,
  accountsLoaded,
  accountsLoading,
  accountsError,
  selectedTokenId,
  dashboardVersion,
  loadAccounts,
  resetDashboardAccountState,
} = useDashboardAccount()
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
const rootRouteMotionKey = computed(() => isControlPanelRoute.value ? 'control-panel' : route.path)
const rootViewComponentKey = computed(() => isControlPanelRoute.value ? 'control-panel-shell' : dashboardViewKey.value)
const isStaff = computed(() => isStaffUser(user.value))
const canControlPanel = computed(() => canAccessControlPanel(user.value))
const isSellerAnalyticsRoute = computed(() => navItems.some(item => item.name === route.name))
const showWorkspaceBar = computed(
  () => isAuthenticated.value && !isControlPanelRoute.value && (!isStaff.value || isSellerAnalyticsRoute.value)
)
const userRoleLabels = computed(() =>
  (user.value?.roles || []).map(role => ROLE_LABELS[role] || role)
)
const userFirstName = computed(() =>
  String(user.value?.full_name || '').trim().split(/\s+/)[0] || 'Пользователь'
)
const currentYear = new Date().getFullYear()
const dashboardNeedsAccount = computed(
  () =>
    showAccountFilter.value &&
    accountsLoaded.value &&
    !accountsLoading.value &&
    !accountsError.value &&
    accounts.value.length === 0
)

const dashboardAccountStateVisible = computed(
  () =>
    showAccountFilter.value &&
    (
      (accountsLoading.value && !accountsLoaded.value) ||
      Boolean(accountsError.value) ||
      dashboardNeedsAccount.value
    )
)

const dashboardAccountIssue = computed(() => {
  const tokens = allWbAccounts.value || []
  if (!tokens.length) {
    return {
      title: 'Нет подключённого кабинета Wildberries',
      message: 'Добавьте кабинет Wildberries в профиле — после проверки система запустит первичную синхронизацию автоматически.',
    }
  }

  const counts = tokens.reduce((result, token) => {
    const key = token.connection_status || (
      token.is_revoked
        ? 'revoked'
        : token.expires_at && new Date(token.expires_at) < new Date()
          ? 'expired'
          : token.is_active === false || token.is_valid === false
            ? 'inactive'
            : token.dashboard_available === false
              ? 'outside_tariff'
              : 'active'
    )
    result[key] = (result[key] || 0) + 1
    return result
  }, {})

  if ((counts.outside_tariff || 0) === tokens.length) {
    return {
      title: tokens.length > 1
        ? 'Кабинеты Wildberries вне лимита тарифа'
        : 'Кабинет Wildberries вне лимита тарифа',
      message: 'Подключение действует, но текущий тариф не даёт использовать этот кабинет в аналитике. Проверьте тариф или состав подключённых кабинетов.',
    }
  }

  const reasons = []
  if (counts.revoked) reasons.push(`отозвано: ${counts.revoked}`)
  if (counts.expired) reasons.push(`истёк срок: ${counts.expired}`)
  if (counts.inactive) reasons.push(`отключено: ${counts.inactive}`)
  if (counts.outside_tariff) reasons.push(`вне лимита тарифа: ${counts.outside_tariff}`)

  if (reasons.length) {
    return {
      title: 'Подключение Wildberries требует внимания',
      message: `${reasons.join(' · ')}. Откройте профиль, чтобы обновить, заменить или проверить подключение.`,
    }
  }

  return {
    title: 'Нет доступного кабинета Wildberries',
    message: 'Проверьте подключение Wildberries и ограничения текущего тарифа в профиле.',
  }
})

watch(
  () => user.value?.id || null,
  (currentUserId, previousUserId) => {
    if (
      currentUserId &&
      previousUserId &&
      currentUserId !== previousUserId
    ) {
      resetDashboardAccountState()
      if (showAccountFilter.value) {
        loadAccounts({ force: true })
      }
    }
  }
)

watch(
  () => [isAuthenticated.value, showAccountFilter.value],
  ([authenticated, shouldLoad]) => {
    if (authenticated && shouldLoad) loadAccounts()
  },
  { immediate: true }
)

watch(
  () => route.fullPath,
  () => closeUserMenu()
)

const showLogin = ref(false)
const showRegister = ref(false)
const userMenuOpen = ref(false)
const userMenuRef = ref(null)

const openLogin = () => { showLogin.value = true }
const openRegister = () => { showRegister.value = true }
const closeUserMenu = () => { userMenuOpen.value = false }
const toggleUserMenu = () => { userMenuOpen.value = !userMenuOpen.value }

const navigateFromUserMenu = async (name) => {
  closeUserMenu()
  await router.push({ name })
}

const handleDocumentPointerDown = (event) => {
  if (!userMenuOpen.value || !userMenuRef.value) return
  if (!userMenuRef.value.contains(event.target)) closeUserMenu()
}

const handleDocumentKeydown = (event) => {
  if (event.key === 'Escape') closeUserMenu()
}

onMounted(() => {
  window.addEventListener('wb:open-login', openLogin)
  window.addEventListener('wb:open-register', openRegister)
  document.addEventListener('pointerdown', handleDocumentPointerDown)
  document.addEventListener('keydown', handleDocumentKeydown)
})

onBeforeUnmount(() => {
  window.removeEventListener('wb:open-login', openLogin)
  window.removeEventListener('wb:open-register', openRegister)
  document.removeEventListener('pointerdown', handleDocumentPointerDown)
  document.removeEventListener('keydown', handleDocumentKeydown)
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
    resetDashboardAccountState()
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

        <div v-if="isAuthenticated && user" ref="userMenuRef" class="user-menu">
          <button
            class="user-menu__trigger"
            type="button"
            aria-label="Меню пользователя"
            :aria-expanded="userMenuOpen ? 'true' : 'false'"
            @click="toggleUserMenu"
          >
            <span class="avatar" aria-hidden="true">{{ user.full_name?.charAt(0) || user.email?.charAt(0) || 'U' }}</span>
            <span class="user-identity">
              <strong>{{ user.full_name || 'Пользователь' }}</strong>
              <small>{{ user.email }}</small>
            </span>
            <span class="chevron" :class="{ 'chevron--open': userMenuOpen }" aria-hidden="true">⌄</span>
          </button>

          <Transition name="user-menu-motion">
            <div v-if="userMenuOpen" class="user-menu__content">
              <div class="user-menu__profile">
                <span class="avatar avatar--menu" aria-hidden="true">{{ user.full_name?.charAt(0) || user.email?.charAt(0) || 'U' }}</span>
                <div class="user-menu__profile-copy">
                  <strong>Аккаунт {{ userFirstName }}</strong>
                  <span>{{ user.email }}</span>
                  <div v-if="userRoleLabels.length" class="user-menu__roles">
                    <span v-for="role in userRoleLabels" :key="role" class="user-role-chip">{{ role }}</span>
                  </div>
                </div>
              </div>

              <div class="menu-section-label">Рабочая область</div>
              <button v-if="isStaff" class="menu-action" type="button" @click="navigateFromUserMenu('staff.home')">
                <span class="menu-action__icon" aria-hidden="true">⌂</span>
                <span><strong>Рабочий стол</strong><small>Приоритеты и инструменты вашей роли</small></span>
              </button>
              <button v-else class="menu-action" type="button" @click="navigateFromUserMenu('dashboard.home')">
                <span class="menu-action__icon" aria-hidden="true">⌂</span>
                <span><strong>Моя аналитика</strong><small>Обзор кабинетов Wildberries</small></span>
              </button>
              <button v-if="isStaff" class="menu-action" type="button" @click="navigateFromUserMenu('dashboard.home')">
                <span class="menu-action__icon" aria-hidden="true">◫</span>
                <span><strong>Клиентская аналитика</strong><small>Вторичный режим для проверки интерфейса</small></span>
              </button>

              <div class="menu-section-label">Мой аккаунт</div>
              <button class="menu-action" type="button" @click="navigateFromUserMenu('dashboard.profile')">
                <span class="menu-action__icon" aria-hidden="true">◎</span>
                <span><strong>{{ isStaff ? 'Профиль аккаунта' : 'Профиль и подключения' }}</strong><small>{{ isStaff ? 'Личные данные и настройки аккаунта' : 'Данные профиля и WB-кабинеты' }}</small></span>
              </button>
              <button class="menu-action" type="button" @click="navigateFromUserMenu('dashboard.account-security')">
                <span class="menu-action__icon" aria-hidden="true">◈</span>
                <span><strong>Безопасность</strong><small>Пароль, email и активные сессии</small></span>
              </button>

              <template v-if="canControlPanel">
                <div class="menu-section-label">Администрирование</div>
                <button class="menu-action" type="button" @click="navigateFromUserMenu('control-panel.index')">
                  <span class="menu-action__icon" aria-hidden="true">⚙</span>
                  <span><strong>Панель управления</strong><small>Пользователи, тарифы и система</small></span>
                </button>
              </template>

              <div class="menu-divider" />
              <button class="menu-action menu-action--danger" type="button" @click="closeUserMenu(); logout()">
                <span class="menu-action__icon" aria-hidden="true">↪</span>
                <span><strong>Выйти из аккаунта</strong><small>Завершить текущую сессию</small></span>
              </button>
            </div>
          </Transition>
        </div>

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
    <section v-if="showWorkspaceBar" class="workspace-bar" aria-label="Навигация аналитики">
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

    <DashboardState
      v-if="showAccountFilter && accountsLoading && !accountsLoaded"
      kind="loading"
    />
    <DashboardState
      v-else-if="showAccountFilter && accountsError"
      kind="error"
      title="Не удалось проверить кабинеты Wildberries"
      :message="accountsError"
      action-label="Повторить"
      @retry="loadAccounts({ force: true })"
    />
    <DashboardState
      v-else-if="dashboardNeedsAccount"
      kind="account"
      :title="dashboardAccountIssue.title"
      :message="dashboardAccountIssue.message"
      action-label="Проверить подключения"
      :action-to="{ name: 'dashboard.profile' }"
    />
    <RouterView v-else v-slot="{ Component }">
      <Transition name="page-motion" mode="out-in">
        <div :key="rootRouteMotionKey" class="route-motion-frame">
          <component :is="Component" :key="rootViewComponentKey" />
        </div>
      </Transition>
    </RouterView>
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

.user-menu__trigger {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 220px;
  padding: 6px 9px;
  border: 0;
  border-radius: 10px;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition: background 220ms ease;
}

.user-menu__trigger:hover,
.user-menu__trigger[aria-expanded="true"] {
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
  transition: transform 220ms ease;
}

.chevron--open {
  transform: rotate(180deg);
}

.user-menu__content {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  min-width: 310px;
  padding: 8px;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  background: var(--card-bg-elevated);
  box-shadow: var(--shadow);
}

.user-menu-motion-enter-active,
.user-menu-motion-leave-active {
  transition: opacity 220ms ease, transform 260ms cubic-bezier(0.22, 1, 0.36, 1);
}

.user-menu-motion-enter-from,
.user-menu-motion-leave-to {
  opacity: 0;
  transform: translateY(-6px) scale(0.985);
}


.user-menu__profile {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 10px 12px;
  margin-bottom: 4px;
  border-radius: 9px;
  background: var(--light-bg);
}
.avatar--menu {
  width: 38px;
  height: 38px;
  flex-basis: 38px;
}
.user-menu__profile-copy {
  min-width: 0;
  display: grid;
  gap: 2px;
}
.user-menu__profile-copy > strong {
  font-size: 13px;
}
.user-menu__profile-copy > span {
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--text-muted);
  font-size: 11px;
}
.user-menu__roles {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 6px;
}
.user-role-chip {
  padding: 3px 6px;
  border: 1px solid color-mix(in srgb, var(--secondary-color) 25%, var(--border-color));
  border-radius: 999px;
  background: color-mix(in srgb, var(--secondary-color) 8%, var(--card-bg));
  color: var(--secondary-color);
  font-size: 10px;
  font-weight: 700;
}
.menu-section-label {
  padding: 9px 10px 4px;
  color: var(--text-subtle);
  font-size: 9px;
  font-weight: 800;
  letter-spacing: .08em;
  text-transform: uppercase;
}
.menu-action {
  width: 100%;
  display: grid;
  grid-template-columns: 24px minmax(0, 1fr);
  align-items: start;
  gap: 8px;
  padding: 9px 10px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--text-color);
  text-align: left;
  cursor: pointer;
}
.menu-action__icon {
  min-height: 22px;
  display: grid;
  place-items: center;
  color: var(--text-muted);
  font-size: 14px;
}
.menu-action > span:last-child {
  min-width: 0;
  display: grid;
  gap: 2px;
}
.menu-action strong {
  font-size: 12px;
  font-weight: 700;
}
.menu-action small {
  color: var(--text-muted);
  font-size: 10px;
  line-height: 1.35;
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
  padding: 10px 12px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(250px, auto);
  align-items: center;
  gap: 18px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  background: var(--header-bg-soft);
  box-shadow: var(--shadow-sm);
}

.workspace-nav {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
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
  min-width: 0;
  justify-self: end;
}

.app-footer {
  padding: 24px;
  color: var(--text-subtle);
  text-align: center;
  font-size: 12px;
}

.route-motion-frame {
  min-width: 0;
  transform-origin: 50% 18%;
  will-change: opacity, transform;
}

.page-motion-enter-active {
  transition:
    opacity 230ms ease-out,
    transform 280ms cubic-bezier(0.22, 1, 0.36, 1);
}

.page-motion-leave-active {
  transition:
    opacity 135ms ease-in,
    transform 155ms ease-in;
}

.page-motion-enter-from {
  opacity: 0;
  transform: translateY(9px) scale(0.996);
}

.page-motion-leave-to {
  opacity: 0;
  transform: translateY(-4px) scale(0.998);
}

@media (prefers-reduced-motion: reduce) {
  .page-motion-enter-active,
  .page-motion-leave-active {
    transition: none;
  }

  .page-motion-enter-from,
  .page-motion-leave-to {
    opacity: 1;
    transform: none;
  }
}

@media (max-width: 900px) {
  .landing-header-nav {
    display: none;
  }

  .workspace-bar {
    grid-template-columns: 1fr;
    align-items: stretch;
  }

  .workspace-account {
    width: 100%;
    justify-self: stretch;
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