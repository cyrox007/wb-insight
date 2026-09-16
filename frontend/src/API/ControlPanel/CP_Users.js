import $api from "..";

export default class CP_Users {
    static async getUserList() {
        return await $api.get('/control-panel/users/')
    }
    static async getUser(userId) {
        return await $api.get(`/control-panel/users/${userId}`)
    }
    static async deleteUser(userId) {
        return await $api.delete(`/control-panel/users/${userId}`)
    }
}
