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

initializeTheme()

const bootstrap = async () => {
	const app = createApp(App)
	app.use(pinia)

	const authStore = useAuthStore(pinia)
	await authStore.restoreSession()

	app.use(router)
	app.mount('#app')
}

bootstrap()
