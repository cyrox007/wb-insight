import $api from '..'

export default class CP_Diagnostics {
	static async search(query, eventLimit = 100) {
		return await $api.get('/control-panel/operations/diagnostics/search', {
			params: { query, event_limit: eventLimit },
		})
	}

	static async findUser(params = {}) {
		return await $api.get('/control-panel/operations/diagnostics/users', { params })
	}

	static async getUser(userId) {
		return await $api.get(`/control-panel/operations/diagnostics/users/${userId}`)
	}

	static async getOperation(operationId) {
		return await $api.get(`/control-panel/operations/diagnostics/operations/${operationId}`)
	}

	static async getRequest(requestId) {
		return await $api.get(`/control-panel/operations/diagnostics/requests/${encodeURIComponent(requestId)}`)
	}

	static async getEvents(params = {}) {
		return await $api.get('/control-panel/operations/diagnostics/events', { params })
	}
}
