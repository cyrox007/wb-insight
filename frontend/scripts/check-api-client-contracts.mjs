import fs from 'node:fs'
import path from 'node:path'

const root = path.resolve('src')
const clients = {
  CP_Mail: path.join(root, 'API/ControlPanel/CP_Mail.js'),
  CP_Users: path.join(root, 'API/ControlPanel/CP_Users.js'),
  CP_Roles: path.join(root, 'API/ControlPanel/CP_Roles.js'),
  ProfileServices: path.join(root, 'API/Dashboard/ProfileServices.js'),
  AccountLifecycleService: path.join(root, 'API/AccountLifecycleService.js'),
}

function walk(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) return walk(full)
    return /\.(vue|js)$/.test(entry.name) ? [full] : []
  })
}

const files = walk(root)
const errors = []

for (const [clientName, clientPath] of Object.entries(clients)) {
  const clientSource = fs.readFileSync(clientPath, 'utf8')
  const implemented = new Set(
    [...clientSource.matchAll(/static\s+async\s+([A-Za-z_$][\w$]*)\s*\(/g)]
      .map((match) => match[1]),
  )

  const referenced = new Map()
  const callPattern = new RegExp(
    `\\b${clientName}\\.([A-Za-z_$][\\w$]*)\\s*\\(`,
    'g',
  )

  for (const file of files) {
    const source = fs.readFileSync(file, 'utf8')
    const executableSource = source
      .replace(/\/\*[\s\S]*?\*\//g, '')
      .replace(/^\s*\/\/.*$/gm, '')
    for (const match of executableSource.matchAll(callPattern)) {
      const method = match[1]
      if (!referenced.has(method)) referenced.set(method, [])
      referenced.get(method).push(path.relative(process.cwd(), file))
    }
  }

  for (const [method, locations] of referenced.entries()) {
    if (!implemented.has(method)) {
      errors.push(
        `${clientName}.${method}() используется, но не реализован в ${path.relative(process.cwd(), clientPath)}\n  места использования: ${[...new Set(locations)].join(', ')}`,
      )
    }
  }
}

const dashboardAccountPath = path.join(root, 'composables/dashboardAccount.js')
const appPath = path.join(root, 'App.vue')
const apiPath = path.join(root, 'API/index.js')
const authServicePath = path.join(root, 'API/AuthService.js')
const authStorePath = path.join(root, 'stores/auth.js')
const cpUsersPath = path.join(root, 'API/ControlPanel/CP_Users.js')
const cpUsersIndexPath = path.join(root, 'pages/ControlPanel/Users/index.vue')
const createStaffUserPath = path.join(root, 'components/UserModals/create_staff_user.vue')
const editUserPath = path.join(root, 'pages/ControlPanel/Users/edit.vue')
const rolesPagePath = path.join(root, 'pages/ControlPanel/Roles/index.vue')
const manageRolesPath = path.join(root, 'components/UserModals/manage_roles.vue')
const cpRolesPath = path.join(root, 'API/ControlPanel/CP_Roles.js')
const tariffsPagePath = path.join(root, 'pages/ControlPanel/Tariffs/index.vue')
const cpTariffsPath = path.join(root, 'API/ControlPanel/CP_Tariffs.js')
const paymentsPath = path.join(root, 'pages/ControlPanel/Payments/index.vue')
const registrationPath = path.join(root, 'components/CustomModals/AuthModals/RegistrationModal.vue')
const sellerProfilePath = path.join(root, 'pages/Dashboard/Profile/index.vue')
const accountLifecyclePath = path.join(root, 'API/AccountLifecycleService.js')
const sellerOnboardingPath = path.join(root, 'components/SellerOnboarding.vue')
const addTokenModalPath = path.join(root, 'components/CustomModals/ProfileModals/AddTokenModal.vue')
const dashboardMainPath = path.join(root, 'pages/Dashboard/Main/index.vue')
const dashboardAccountSource = fs.readFileSync(dashboardAccountPath, 'utf8')
const appSource = fs.readFileSync(appPath, 'utf8')
const apiSource = fs.readFileSync(apiPath, 'utf8')
const authServiceSource = fs.readFileSync(authServicePath, 'utf8')
const authStoreSource = fs.readFileSync(authStorePath, 'utf8')
const cpUsersSource = fs.readFileSync(cpUsersPath, 'utf8')
const cpUsersIndexSource = fs.readFileSync(cpUsersIndexPath, 'utf8')
const createStaffUserSource = fs.readFileSync(createStaffUserPath, 'utf8')
const editUserSource = fs.readFileSync(editUserPath, 'utf8')
const rolesPageSource = fs.readFileSync(rolesPagePath, 'utf8')
const manageRolesSource = fs.readFileSync(manageRolesPath, 'utf8')
const cpRolesSource = fs.readFileSync(cpRolesPath, 'utf8')
const tariffsPageSource = fs.readFileSync(tariffsPagePath, 'utf8')
const cpTariffsSource = fs.readFileSync(cpTariffsPath, 'utf8')
const paymentsSource = fs.readFileSync(paymentsPath, 'utf8')
const registrationSource = fs.readFileSync(registrationPath, 'utf8')
const sellerProfileSource = fs.readFileSync(sellerProfilePath, 'utf8')
const accountLifecycleSource = fs.readFileSync(accountLifecyclePath, 'utf8')
const sellerOnboardingSource = fs.readFileSync(sellerOnboardingPath, 'utf8')
const addTokenModalSource = fs.readFileSync(addTokenModalPath, 'utf8')
const dashboardMainSource = fs.readFileSync(dashboardMainPath, 'utf8')

const sessionIsolationChecks = [
  {
    ok: dashboardAccountSource.includes('export function resetDashboardAccountState()'),
    message: 'Кэш кабинетов должен иметь явную функцию сброса между сессиями.',
  },
  {
    ok:
      dashboardAccountSource.includes('let stateGeneration = 0') &&
      dashboardAccountSource.includes('requestGeneration !== stateGeneration'),
    message: 'Поздний ответ запроса предыдущей сессии должен отбрасываться по поколению состояния.',
  },
  {
    ok:
      dashboardAccountSource.includes('if (loadingPromise && force)') &&
      dashboardAccountSource.includes('stateGeneration += 1'),
    message: 'Принудительное обновление должно инвалидировать незавершённый запрос предыдущего состояния.',
  },
  {
    ok:
      dashboardAccountSource.includes('token.connection_status') &&
      dashboardAccountSource.includes("connectionStatus(token) === 'active'"),
    message: 'Список аналитики должен использовать единый статус доступности подключения Wildberries.',
  },
  {
    ok:
      dashboardAccountSource.includes("persistSelectedTokenId('')") &&
      dashboardAccountSource.includes('allWbAccounts.value = []') &&
      dashboardAccountSource.includes('accounts.value = []'),
    message: 'Сброс сессии должен очищать выбранный кабинет и оба списка подключений.',
  },
  {
    ok: /finally\s*\{[\s\S]*?resetDashboardAccountState\(\)[\s\S]*?authStore\.logout\(\)/.test(appSource),
    message: 'Штатный выход должен очистить кэш кабинетов до завершения клиентской сессии.',
  },
  {
    ok: appSource.includes('currentUserId !== previousUserId'),
    message: 'Смена пользователя без перезагрузки страницы должна сбрасывать кэш кабинетов.',
  },
]

for (const check of sessionIsolationChecks) {
  if (!check.ok) errors.push(check.message)
}

const authSessionRaceChecks = [
  {
    ok:
      apiSource.includes('let sessionGeneration = 0') &&
      apiSource.includes('requestGeneration !== sessionGeneration'),
    message: 'Ответ обновления старого поколения сессии должен отбрасываться.',
  },
  {
    ok:
      apiSource.includes('let refreshPromise = null') &&
      apiSource.includes('refreshPromise === requestPromise'),
    message: 'Все refresh-запросы должны использовать единый promise без гонки очистки.',
  },
  {
    ok:
      apiSource.includes("const STALE_REFRESH_CODE = 'STALE_SESSION_REFRESH'") &&
      apiSource.includes('isStaleSessionRefreshError(refreshError)'),
    message: 'Устаревший refresh должен отличаться от реальной ошибки текущей сессии.',
  },
  {
    ok:
      apiSource.includes("'/auth/login'") &&
      apiSource.includes("'/auth/logout'") &&
      apiSource.includes('SESSION_REFRESH_EXCLUDED_ENDPOINTS.has(requestPath)'),
    message: 'Login/logout и публичные auth-маршруты не должны запускать автоматический refresh после 401.',
  },
  {
    ok:
      authServiceSource.includes('invalidateSessionRefresh()') &&
      /static async logout\(\)[\s\S]*?invalidateSessionRefresh\(\)[\s\S]*?\/auth\/logout/.test(authServiceSource),
    message: 'Logout должен инвалидировать незавершённый refresh до серверного запроса.',
  },
  {
    ok:
      authStoreSource.includes('establishClientSession(accessToken)') &&
      authStoreSource.includes('isStaleSessionRefreshError(error)'),
    message: 'Новая login-сессия должна начинать новое поколение, а поздний restore не должен очищать её.',
  },
]

for (const check of authSessionRaceChecks) {
  if (!check.ok) errors.push(check.message)
}

const permanentUserDeleteChecks = [
  {
    ok:
      cpUsersSource.includes('/control-panel/users/${userId}/purge') &&
      cpUsersSource.includes('confirm_email: confirmEmail'),
    message: 'Permanent delete должен использовать отдельный purge-маршрут и подтверждение email.',
  },
  {
    ok:
      editUserSource.includes('const canPermanentlyDelete = computed') &&
      editUserSource.includes('targetUser.value.is_active === false') &&
      editUserSource.includes('!isSelf.value'),
    message: 'Кнопка необратимого удаления должна быть доступна только для неактивной чужой учётной записи.',
  },
  {
    ok:
      editUserSource.includes('confirmation !== expectedEmail') &&
      editUserSource.includes('CP_Users.permanentlyDeleteUser'),
    message: 'Интерфейс должен требовать точное подтверждение email до вызова permanent delete.',
  },
  {
    ok:
      editUserSource.includes('Удалить пользователя навсегда') &&
      editUserSource.includes('Аккаунт и связанные пользовательские данные будут удалены необратимо'),
    message: 'Опасная операция должна иметь отдельное явное предупреждение о необратимости.',
  },
]

for (const check of permanentUserDeleteChecks) {
  if (!check.ok) errors.push(check.message)
}

const roleManagementUiChecks = [
  {
    ok:
      rolesPageSource.includes('Роли суммируются, а не заменяют друг друга.') &&
      rolesPageSource.includes('Текущие назначения') &&
      !rolesPageSource.includes('selectedRoles'),
    message: 'Основной экран ролей должен показывать только фактические назначения и не содержать предвыбранных будущих ролей.',
  },
  {
    ok:
      rolesPageSource.includes('Справочник ролей и permissions') &&
      rolesPageSource.includes('<details class="cp-card role-reference">'),
    message: 'Техническая матрица permissions должна быть свёрнутым справочным блоком.',
  },
  {
    ok:
      manageRolesSource.includes('Роли суммируются.') &&
      manageRolesSource.includes('Текущие роли') &&
      manageRolesSource.includes('Добавить ещё одну роль') &&
      manageRolesSource.includes("role === 'super_admin' && isSelf.value"),
    message: 'Изменение ролей должно выполняться отдельной модалкой с текущим состоянием и защитой self-demotion.',
  },
  {
    ok:
      manageRolesSource.includes('Полный системный доступ') &&
      manageRolesSource.includes('Email для подтверждения') &&
      cpRolesSource.includes('confirm_email'),
    message: 'Назначение super_admin должно требовать явное подтверждение email целевого пользователя.',
  },
  {
    ok:
      editUserSource.includes('ManageRolesModal') &&
      editUserSource.includes('Показаны только роли, назначенные сейчас.') &&
      !editUserSource.includes('AssignRoleModal'),
    message: 'Карточка пользователя должна использовать единый безопасный редактор ролей.',
  },
]

for (const check of roleManagementUiChecks) {
  if (!check.ok) errors.push(check.message)
}

const paymentProviderUiChecks = [
  {
    ok:
      paymentsSource.includes('const sberGatewayHint = computed') &&
      paymentsSource.includes('https://ecomift.sberbank.ru/ecomm/gw/partner/api/v1') &&
      paymentsSource.includes('https://ecommerce.sberbank.ru/ecomm/gw/partner/api/v1'),
    message: 'Control Panel должен явно показывать допустимые Sber gateway для test/live.',
  },
  {
    ok:
      paymentsSource.includes('произвольные узлы для реквизитов мерчанта запрещены') &&
      paymentsSource.includes('maxlength="3"') &&
      paymentsSource.includes('pattern="\\d{3}"'),
    message: 'Форма Sber должна объяснять host policy и ограничивать код валюты тремя цифрами.',
  },
]

for (const check of paymentProviderUiChecks) {
  if (!check.ok) errors.push(check.message)
}

const registrationPreflightChecks = [
  {
    ok:
      registrationSource.includes('Не удалось проверить email. Повторите попытку.') &&
      registrationSource.includes('Не удалось проверить ИНН. Повторите попытку.'),
    message: 'Email и ИНН availability-проверки должны закрывать шаг регистрации при сетевой ошибке.',
  },
  {
    ok:
      registrationSource.includes('Не удалось проверить номер телефона. Повторите попытку.') &&
      registrationSource.includes('value = value.slice(0, 10)'),
    message: 'Телефон должен fail-closed проверяться и ограничиваться десятью локальными цифрами.',
  },
  {
    ok: !registrationSource.includes('console.log(value)'),
    message: 'Форма регистрации не должна выводить номер телефона в browser console.',
  },
]

for (const check of registrationPreflightChecks) {
  if (!check.ok) errors.push(check.message)
}

const registrationPersistenceChecks = [
  {
    ok:
      !registrationSource.includes('formData.bank_account') &&
      !registrationSource.includes('formData.bik') &&
      !registrationSource.includes('Расчётный счёт') &&
      !registrationSource.includes('БИК банка'),
    message: 'Регистрация не должна собирать банковские реквизиты, которые backend не сохраняет.',
  },
]

for (const check of registrationPersistenceChecks) {
  if (!check.ok) errors.push(check.message)
}

const sellerProfileIdentityChecks = [
  {
    ok:
      !sellerProfileSource.includes('payload.entity_type') &&
      !sellerProfileSource.includes('v-model="profileForm.entity_type"'),
    message: 'Self-service профиль не должен отправлять или редактировать тип продавца.',
  },
  {
    ok:
      sellerProfileSource.includes('Изменение типа продавца требует административной проверки юридических реквизитов.') &&
      sellerProfileSource.includes('{{ entityTypeLabel }}'),
    message: 'Тип продавца должен отображаться read-only с объяснением административной проверки.',
  },
]

for (const check of sellerProfileIdentityChecks) {
  if (!check.ok) errors.push(check.message)
}

const emailChangeChecks = [
  {
    ok:
      sellerProfileSource.includes('ProfileServices.requestEmailChange(email)') &&
      sellerProfileSource.includes('user.pending_email'),
    message: 'Профиль должен использовать подтверждаемую смену email и показывать pending-адрес.',
  },
  {
    ok:
      sellerProfileSource.includes('ProfileServices.cancelEmailChange()') &&
      sellerProfileSource.includes('Отменить смену'),
    message: 'Профиль должен позволять безопасно отменить ожидающую смену email.',
  },
  {
    ok:
      sellerProfileSource.includes('Email меняется после подтверждения нового адреса. Телефон — через администратора.') &&
      !sellerProfileSource.includes('Email и телефон меняются через отдельное подтверждение.'),
    message: 'Профиль не должен обещать несуществующее self-service подтверждение телефона.',
  },
]

for (const check of emailChangeChecks) {
  if (!check.ok) errors.push(check.message)
}

const accountSecurityEmailChangeChecks = [
  {
    ok:
      accountLifecycleSource.includes("'/dashboard/profile/email-change/request'") &&
      accountLifecycleSource.includes("'/dashboard/profile/email-change/cancel'"),
    message: 'Страница безопасности аккаунта должна использовать канонический P97 flow смены email.',
  },
  {
    ok: !accountLifecycleSource.includes('/account/email/change-request'),
    message: 'Клиентский API не должен возвращаться к устаревшему параллельному маршруту смены email.',
  },
]

for (const check of accountSecurityEmailChangeChecks) {
  if (!check.ok) errors.push(check.message)
}

const sellerOnboardingChecks = [
  {
    ok:
      dashboardMainSource.includes('<SellerOnboarding') &&
      dashboardMainSource.includes("DashboardService.get_sync_status()") &&
      dashboardMainSource.includes("code === 'NO_VALID_TOKENS'"),
    message: 'Главный дашборд должен показывать onboarding, обновлять прогресс синхронизации и отдельно обрабатывать отсутствие кабинета.',
  },
  {
    ok:
      sellerOnboardingSource.includes("query: { tab: 'connections' }") &&
      sellerOnboardingSource.includes("query: { tab: 'costs' }") &&
      sellerOnboardingSource.includes('Скрыть подсказки'),
    message: 'Onboarding должен вести сразу к подключению WB и себестоимости и позволять скрыть подсказки после получения данных.',
  },
  {
    ok:
      sellerProfileSource.includes('route.query.tab') &&
      sellerProfileSource.includes('await selectTab(requestedTab)'),
    message: 'Профиль должен открывать нужную вкладку по глубокой ссылке из onboarding.',
  },
  {
    ok:
      addTokenModalSource.includes('Проверить и подключить') &&
      addTokenModalSource.includes('WB_TOKEN_PERMISSIONS_MISSING') &&
      addTokenModalSource.includes('WB_TOKEN_MUST_BE_READ_ONLY') &&
      addTokenModalSource.includes('Контент') &&
      addTokenModalSource.includes('Финансы'),
    message: 'Подключение Wildberries должно содержать пошаговую инструкцию и человекочитаемую диагностику прав токена.',
  },
]

for (const check of sellerOnboardingChecks) {
  if (!check.ok) errors.push(check.message)
}

const staffWbConnectionChecks = [
  {
    ok:
      appSource.includes("query: { tab: 'connections' }") &&
      appSource.includes('Открыть кабинеты WB') &&
      appSource.includes('connectionCountLabel'),
    message: 'Состояние недоступного WB-кабинета должно вести прямо в управление подключениями и использовать корректные русские склонения.',
  },
  {
    ok:
      sellerProfileSource.includes("const staffTabs = [") &&
      sellerProfileSource.includes("{ key: 'connections', label: 'Кабинеты WB' }") &&
      sellerProfileSource.includes("tabs.value.some(tab => tab.key === requestedTab)"),
    message: 'Staff-профиль должен открывать собственные WB-подключения и поддерживать прямую ссылку на вкладку connections.',
  },
  {
    ok:
      sellerProfileSource.includes('ProfileServices.check_user_token(id)') &&
      sellerProfileSource.includes('Проверить статус') &&
      sellerProfileSource.includes('<AddTokenModal v-if="showAddTokenModal"'),
    message: 'Вкладка подключений должна позволять staff-пользователю добавить токен и повторно проверить его статус.',
  },
]

for (const check of staffWbConnectionChecks) {
  if (!check.ok) errors.push(check.message)
}

const controlPanelUserCrudChecks = [
  {
    ok:
      cpUsersSource.includes('createStaffUser(payload)') &&
      cpUsersSource.includes("post('/control-panel/users/'") &&
      cpUsersSource.includes('permanentlyDeleteUser'),
    message: 'Клиент Control Panel должен поддерживать создание служебного аккаунта и необратимое удаление.',
  },
  {
    ok:
      cpUsersIndexSource.includes('Добавить сотрудника') &&
      cpUsersIndexSource.includes('Деактивировать') &&
      cpUsersIndexSource.includes('Удалить навсегда') &&
      cpUsersIndexSource.includes('permanentlyDeleteConfirmed'),
    message: 'Список пользователей должен явно показывать создание, деактивацию и необратимое удаление.',
  },
  {
    ok:
      createStaffUserSource.includes('Клиентские аккаунты здесь не создаются') &&
      createStaffUserSource.includes('CP_Users.createStaffUser') &&
      createStaffUserSource.includes('Сгенерировать'),
    message: 'Создание служебного аккаунта должно быть отдельным потоком и не подменять клиентскую регистрацию.',
  },
]

for (const check of controlPanelUserCrudChecks) {
  if (!check.ok) errors.push(check.message)
}

const controlPanelUserListUxChecks = [
  {
    ok:
      cpUsersIndexSource.includes('scheduleFilterReload') &&
      cpUsersIndexSource.includes('watch(') &&
      !cpUsersIndexSource.includes('text="Показать"'),
    message: 'Фильтры списка пользователей должны применяться автоматически без отдельной кнопки «Показать».',
  },
  {
    ok:
      cpUsersIndexSource.includes("toggleSort('user')") &&
      cpUsersIndexSource.includes("toggleSort('email')") &&
      cpUsersIndexSource.includes("toggleSort('created_at')") &&
      cpUsersIndexSource.includes('sort_by: sorting.by') &&
      cpUsersIndexSource.includes('sort_order: sorting.order'),
    message: 'Список пользователей должен передавать backend двустороннюю сортировку основных колонок.',
  },
  {
    ok:
      cpUsersIndexSource.includes("stage: user.is_active ? 'deactivate' : 'confirm'") &&
      cpUsersIndexSource.includes('Деактивировать и продолжить') &&
      cpUsersIndexSource.includes('Удалить навсегда'),
    message: 'Удаление пользователя должно быть явным двухшаговым сценарием для активного аккаунта.',
  },
  {
    ok:
      cpUsersIndexSource.includes('let loadGeneration = 0') &&
      cpUsersIndexSource.includes('generation !== loadGeneration'),
    message: 'Автофильтрация должна отбрасывать поздние ответы предыдущих запросов.',
  },
]

for (const check of controlPanelUserListUxChecks) {
  if (!check.ok) errors.push(check.message)
}

const tariffLifecycleUiChecks = [
  {
    ok:
      cpTariffsSource.includes('deleteTariff(tariffId)') &&
      cpTariffsSource.includes("delete(`/control-panel/tariffs/${tariffId}`)"),
    message: 'Клиент Control Panel должен поддерживать удаление тарифа через защищённый backend endpoint.',
  },
  {
    ok:
      tariffsPageSource.includes('Активный тариф сначала деактивируется.') &&
      tariffsPageSource.includes("text=\"Удалить…\"") &&
      tariffsPageSource.includes('deleteTariffConfirmed'),
    message: 'Экран тарифов должен явно показывать lifecycle деактивация → удаление.',
  },
  {
    ok:
      tariffsPageSource.includes('Для подтверждения введите код') &&
      tariffsPageSource.includes('Связанные записи: подписки') &&
      tariffsPageSource.includes("tariff-row--system"),
    message: 'Удаление тарифа должно требовать код, объяснять связанные данные и защищать системный demo.',
  },
  {
    ok:
      tariffsPageSource.includes('class="cp-card tariff-list"') &&
      tariffsPageSource.includes('class="tariff-row"') &&
      !tariffsPageSource.includes('cp-tariff-grid'),
    message: 'Тарифы должны отображаться компактным стабильным списком вместо растягивающейся сетки карточек.',
  },
]

for (const check of tariffLifecycleUiChecks) {
  if (!check.ok) errors.push(check.message)
}

if (errors.length) {
  console.error('Проверка контрактов клиентского приложения завершилась ошибкой:\n')
  console.error(errors.join('\n\n'))
  process.exit(1)
}

console.log('Контракты клиентского приложения согласованы.')
