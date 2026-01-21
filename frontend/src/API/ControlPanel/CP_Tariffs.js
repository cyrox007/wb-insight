import $api from "..";

export default class CP_Tariffs {
    static async getTariffList() {
		return await $api.get('/control-panel/tariffs')
	}
	static async getTariff(tariffId) {
		return await $api.get(`/control-panel/tariffs/${tariffId}`)
	}
	static async createTariff(tariff) {
		return await $api.post('/control-panel/tariffs/create', tariff)
	}
	static async updateTariffStatus(tariffId, newStatus) {
		return await $api.put(`/control-panel/tariffs/${tariffId}/update-status`, {status: newStatus})
	}
	static async editTariff(tariffId, tariff) {
		return await $api.put(`/control-panel/tariffs/${tariffId}/edit`, tariff)
	}
	static async createLimit(tariffId, limit) {
		return await $api.post(`/control-panel/tariffs/${tariffId}/limits/create`, { ...limit});
	}
	static async updateLimit(tariffId, limitId, limitData) {
		return await $api.put(`/control-panel/tariffs/${tariffId}/limits/${limitId}/edit`, {...limitData});
	}
	static async deleteLimit(tariffId, limitId) {
		return await $api.delete(`/control-panel/tariffs/${tariffId}/limits/${limitId}/delete`);
	}
}