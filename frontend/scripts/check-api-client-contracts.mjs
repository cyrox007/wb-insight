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
const dashboardAccountSource = fs.readFileSync(dashboardAccountPath, 'utf8')
const appSource = fs.readFileSync(appPath, 'utf8')

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

if (errors.length) {
  console.error('Проверка контрактов клиентского приложения завершилась ошибкой:\n')
  console.error(errors.join('\n\n'))
  process.exit(1)
}

console.log('Контракты клиентского приложения согласованы.')
