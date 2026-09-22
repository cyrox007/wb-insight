import { computed, readonly, ref } from 'vue'

const STORAGE_KEY = 'wb-theme'
const THEME_LIGHT = 'light'
const THEME_DARK = 'dark'
const COOKIE_MAX_AGE = 60 * 60 * 24 * 365

const theme = ref(THEME_LIGHT)
let initialized = false
let mediaQuery = null

const getThemeCookie = () => {
  if (typeof document === 'undefined') return null
  const prefix = `${STORAGE_KEY}=`
  const value = document.cookie
    .split(';')
    .map(item => item.trim())
    .find(item => item.startsWith(prefix))
    ?.slice(prefix.length)
  return value === THEME_LIGHT || value === THEME_DARK ? value : null
}

const persistThemeCookie = (value) => {
  if (typeof document === 'undefined') return
  const secure = typeof window !== 'undefined' && window.location.protocol === 'https:' ? '; Secure' : ''
  document.cookie = `${STORAGE_KEY}=${value}; Path=/; Max-Age=${COOKIE_MAX_AGE}; SameSite=Lax${secure}`
}

const getStoredTheme = () => {
  try {
    const value = localStorage.getItem(STORAGE_KEY)
    if (value === THEME_LIGHT || value === THEME_DARK) return value
  } catch {
    // Fall back to the host cookie below.
  }

  const cookieTheme = getThemeCookie()
  if (cookieTheme) {
    try {
      localStorage.setItem(STORAGE_KEY, cookieTheme)
    } catch {
      // Cookie-backed persistence is sufficient when localStorage is unavailable.
    }
  }
  return cookieTheme
}

const getSystemTheme = () => {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return THEME_LIGHT
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? THEME_DARK : THEME_LIGHT
}

const applyTheme = (value) => {
  theme.value = value
  if (typeof document !== 'undefined') {
    document.documentElement.dataset.theme = value
    document.documentElement.style.colorScheme = value
    const themeColor = document.getElementById('theme-color')
    if (themeColor) themeColor.content = value === THEME_DARK ? '#111720' : '#f5f7fb'
  }
}

const handleSystemThemeChange = (event) => {
  if (getStoredTheme()) return
  applyTheme(event.matches ? THEME_DARK : THEME_LIGHT)
}

export const initializeTheme = () => {
  if (initialized) return theme.value

  const storedTheme = getStoredTheme()
  applyTheme(storedTheme || getSystemTheme())

  if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
    mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
    mediaQuery.addEventListener?.('change', handleSystemThemeChange)
  }

  initialized = true
  return theme.value
}

export const setTheme = (value) => {
  const normalized = value === THEME_DARK ? THEME_DARK : THEME_LIGHT
  try {
    localStorage.setItem(STORAGE_KEY, normalized)
  } catch {
    // Cookie-backed persistence below still keeps the preference on this host.
  }
  persistThemeCookie(normalized)
  applyTheme(normalized)
}

export const toggleTheme = () => {
  setTheme(theme.value === THEME_DARK ? THEME_LIGHT : THEME_DARK)
}

export const useTheme = () => {
  if (!initialized) initializeTheme()

  return {
    theme: readonly(theme),
    isDark: computed(() => theme.value === THEME_DARK),
    setTheme,
    toggleTheme,
  }
}
