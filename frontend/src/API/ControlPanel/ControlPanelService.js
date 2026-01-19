import $api from "..";

export default class ControlPanelService {
    static async getControlPanel() {
        return await $api.get('/control-panel');
    }
    static async getUserList() {
        return await $api.get('/control-panel/users')
    }
    static async getUserByUuid(uuid) {
        return await $api.get(`/control-panel/users/${uuid}`)
    }

    static async getTariffList() {
        return await $api.get('/control-panel/tariffs')
    }

    static async createTariff(tariff) {
        return await $api.post('/control-panel/tariffs/create', tariff)
    }
    static async updateTariffStatus(tariffId, newStatus) {
        return await $api.put(`/control-panel/tariffs/${tariffId}/update-status`, {status: newStatus})
    }
}