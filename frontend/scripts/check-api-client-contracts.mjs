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
        `${clientName}.${method}() is referenced but not implemented in ${path.relative(process.cwd(), clientPath)}\n  used by: ${[...new Set(locations)].join(', ')}`,
      )
    }
  }
}

if (errors.length) {
  console.error('Control Panel API client contract check failed:\n')
  console.error(errors.join('\n\n'))
  process.exit(1)
}

console.log('Control Panel API client contracts are consistent.')
