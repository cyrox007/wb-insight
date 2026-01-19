export default class CP_Users {
	static async getUserList() {
		return await $api.get('/control-panel/users')
	}
	static async getUserByUuid(uuid) {
		return await $api.get(`/control-panel/users/${uuid}`)
	}
}