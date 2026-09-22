import { createApp } from 'vue'

import App from './App.vue'
import router from './router'
import { pinia } from './stores/pinia'
import { useAuthStore } from './stores/auth'
import { initializeTheme } from './composables/theme'

import './styles/variables.css'
import './styles/base.css'
import './styles/control-panel.css'
import './styles/control-panel-forms.css'
import './styles/control-panel-polish.css'

const enforceCanonicalHttps = () => {
	if (
		!import.meta.env.PROD ||
		typeof window === 'undefined' ||
		window.location.protocol !== 'http:'
	) {
		return false
	}

	const hostname = window.location.hostname
	if (hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '::1') {
		return false
	}

	const target = new URL(window.location.href)
	target.protocol = 'https:'
	if (target.port === '80') target.port = ''
	window.location.replace(target.toString())
	return true
}

const redirectedToHttps = enforceCanonicalHttps()

if (!redirectedToHttps) initializeTheme()

const initializeSmoothAnchorScrolling = () => {
	if (typeof document === 'undefined') return

	const reducedMotion = () =>
		typeof window.matchMedia === 'function' &&
		window.matchMedia('(prefers-reduced-motion: reduce)').matches

	const easeInOutCubic = (progress) =>
		progress < 0.5
			? 4 * progress * progress * progress
			: 1 - Math.pow(-2 * progress + 2, 3) / 2

	document.addEventListener('click', (event) => {
		const link = event.target.closest?.('a[href^="#"]')
		if (!link) return

		const hash = link.getAttribute('href')
		if (!hash || hash === '#') return

		const target = document.querySelector(hash)
		if (!target) return

		event.preventDefault()

		const headerOffset = 84
		const startY = window.scrollY
		const targetY = Math.max(0, target.getBoundingClientRect().top + startY - headerOffset)

		if (reducedMotion()) {
			window.scrollTo(0, targetY)
			history.pushState(null, '', hash)
			return
		}

		const distance = targetY - startY
		const duration = 620
		const startedAt = performance.now()

		const step = (now) => {
			const elapsed = now - startedAt
			const progress = Math.min(1, elapsed / duration)
			window.scrollTo(0, startY + distance * easeInOutCubic(progress))

			if (progress < 1) {
				requestAnimationFrame(step)
				return
			}

			history.pushState(null, '', hash)
		}

		requestAnimationFrame(step)
	})
}

if (!redirectedToHttps) initializeSmoothAnchorScrolling()

const bootstrap = async () => {
	const app = createApp(App)
	app.use(pinia)

	const authStore = useAuthStore(pinia)
	await authStore.restoreSession()

	app.use(router)
	app.mount('#app')
}

if (!redirectedToHttps) bootstrap()
