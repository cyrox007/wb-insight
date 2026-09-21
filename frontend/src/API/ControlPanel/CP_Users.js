import $api from "..";

export default class CP_Users {
    static async getUserList() {
        return await $api.get('/control-panel/users/')
    }
    static async getUser(userId) {
        return await $api.get(`/control-panel/users/${userId}`)
    }
    static async updateUser(userId, payload) {
        return await $api.put(`/control-panel/users/${userId}`, payload)
    }
    static async reactivateUser(userId) {
        return await $api.post(`/control-panel/users/${userId}/reactivate`)
    }
    static async revokeSessions(userId) {
        return await $api.post(`/control-panel/users/${userId}/revoke-sessions`)
    }
    static async deleteUser(userId) {
        return await $api.delete(`/control-panel/users/${userId}`)
    }
}
