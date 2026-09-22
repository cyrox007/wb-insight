import $api from "..";

export default class CP_Users {
    static async getUserList(params = {}) {
        return await $api.get('/control-panel/users/', { params })
    }

    static async getUser(userId) {
        return await $api.get(`/control-panel/users/${userId}`)
    }

    static async getUserByUuid(userId) {
        return await this.getUser(userId)
    }

    static async updateUser(userId, payload) {
        return await $api.put(`/control-panel/users/${userId}`, payload)
    }

    static async verifyEmail(userId, reason = '') {
        return await $api.post(`/control-panel/users/${userId}/verify-email`, { reason })
    }

    static async reactivateUser(userId, reason = '') {
        return await $api.post(`/control-panel/users/${userId}/reactivate`, { reason })
    }

    static async revokeSessions(userId, reason = '') {
        return await $api.post(`/control-panel/users/${userId}/revoke-sessions`, { reason })
    }

    static async deactivateUser(userId) {
        return await $api.delete(`/control-panel/users/${userId}`)
    }

    static async deleteUser(userId) {
        return await this.deactivateUser(userId)
    }

    static async permanentlyDeleteUser(userId, confirmEmail, reason = '') {
        return await $api.delete(`/control-panel/users/${userId}/purge`, {
            data: {
                confirm_email: confirmEmail,
                reason,
            },
        })
    }

    static async getLifecycleEvents(userId) {
        return await $api.get(`/control-panel/users/${userId}/lifecycle-events`)
    }
}
