import fs from 'node:fs'
import path from 'node:path'

const root = path.resolve('src')
const clients = {
  CP_Mail: path.join(root, 'API/ControlPanel/CP_Mail.js'),
  CP_Users: path.join(root, 'API/ControlPanel/CP_Users.js'),
  CP_Roles: path.join(root, 'API/ControlPanel/CP_Roles.js'),
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
const dashboardAccountSource = fs.readFileSync(dashboardAccountPath, 'utf8')
const appSource = fs.readFileSync(appPath, 'utf8')
const apiSource = fs.readFileSync(apiPath, 'utf8')
const authServiceSource = fs.readFileSync(authServicePath, 'utf8')
const authStoreSource = fs.readFileSync(authStorePath, 'utf8')

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

if (errors.length) {
  console.error('Проверка контрактов клиентского приложения завершилась ошибкой:\n')
  console.error(errors.join('\n\n'))
  process.exit(1)
}

console.log('Контракты клиентского приложения согласованы.')
