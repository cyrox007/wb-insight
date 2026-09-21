import { computed, readonly, ref } from 'vue'

const STORAGE_KEY = 'wb-theme'
const THEME_LIGHT = 'light'
const THEME_DARK = 'dark'

const theme = ref(THEME_LIGHT)
let initialized = false
let mediaQuery = null

const getStoredTheme = () => {
  try {
    const value = localStorage.getItem(STORAGE_KEY)
    return value === THEME_LIGHT || value === THEME_DARK ? value : null
  } catch {
    return null
  }
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
    // Theme persistence is optional; applying it for this session still works.
  }
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
