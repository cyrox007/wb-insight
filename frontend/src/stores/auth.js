import { ref, computed } from 'vue'
import { defineStore } from 'pinia'

export const useAuthStore = defineStore('auth', {
	state: () => ({
		isAuthenticated: localStorage.getItem('access_token') ? true : false,
		user: (localStorage.getItem('user')) ? JSON.parse(localStorage.getItem('user')) : null,
	}),
	getters: {
		isAuthSatus: (state) => state.isAuthenticated,
		getUser: (state) => state.user,
	},
	actions: {
		login(user) {
			if (user) {
				this.isAuthenticated = true
				this.user = user
			}
		},
		logout() {
			if (this.isAuthenticated) {
				this.isAuthenticated = false
				this.user = null
			}
		},
	},
})
