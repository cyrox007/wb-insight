import { defineStore } from 'pinia'
import AuthService from '@/API/AuthService'
import { clearClientSession, setAccessToken } from '@/API'
import { purgeLegacyPersistentAuth } from '@/security/session'

export const useAuthStore = defineStore('auth', {
	state: () => ({
		isAuthenticated: false,
		user: null,
		initialized: false,
	}),
	getters: {
		isAuthSatus: (state) => state.isAuthenticated,
		getUser: (state) => state.user,
		isInitialized: (state) => state.initialized,
	},
	actions: {
		applySession(payload) {
			const accessToken = payload?.access_token
			const user = payload?.user
			if (!accessToken || !user) {
				this.clearSession()
				return false
			}
			setAccessToken(accessToken)
			this.isAuthenticated = true
			this.user = user
			return true
		},
		async restoreSession() {
			if (this.initialized) return this.isAuthenticated

			purgeLegacyPersistentAuth()
			try {
				const response = await AuthService.refresh()
				return this.applySession(response.data)
			} catch {
				this.clearSession()
				return false
			} finally {
				this.initialized = true
			}
		},
		login(payload) {
			const applied = this.applySession(payload)
			this.initialized = true
			return applied
		},
		updateUser(user) {
			if (!this.isAuthenticated || !user) return false
			this.user = { ...(this.user || {}), ...user }
			return true
		},
		clearSession() {
			clearClientSession()
			this.isAuthenticated = false
			this.user = null
		},
		logout() {
			this.clearSession()
			this.initialized = true
		},
	},
})
