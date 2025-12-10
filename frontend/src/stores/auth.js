import { ref, computed } from 'vue'
import { defineStore } from 'pinia'

export const useAuthStore = defineStore('auth', {
    state: () => ({
        isAuthenticated: false,
        user: null
    }),
    getters: {
        isAuthSatus: (state) => state.isAuthenticated,
        user: (state) => state.user,
    },
    actions: {
        login(user) {
            if (user) {
                this.isAuthenticated = true;
                this.user = user;
            }
        },
        logout() {
            if (this.isAuthenticated) {
                this.isAuthenticated = false;
                this.user = null;
            }
        }
    }
});