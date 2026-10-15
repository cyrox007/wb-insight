import $api from '..'

export default class CP_Diagnostics {
	static async findUser(params = {}) {
		return await $api.get('/control-panel/operations/diagnostics/users', { params })
	}

	static async getUser(userId) {
		return await $api.get(`/control-panel/operations/diagnostics/users/${userId}`)
	}

	static async getOperation(operationId) {
		return await $api.get(`/control-panel/operations/diagnostics/operations/${operationId}`)
	}

	static async getEvents(params = {}) {
		return await $api.get('/control-panel/operations/diagnostics/events', { params })
	}
}
