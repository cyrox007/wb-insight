import $api from "..";

export default class CP_Users {
	static async getUserList() {
		return await $api.get('/control-panel/users')
	}
	static async getUserByUuid(uuid) {
		return await $api.get(`/control-panel/users/${uuid}`)
	}
	static async updateUser(uuid, data) {
		return await $api.put(`/control-panel/users/${uuid}`, data)
	}
}