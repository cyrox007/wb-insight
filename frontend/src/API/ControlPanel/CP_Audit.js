import $api from '..'

export default class CP_Audit {
	static async getEvents(params = {}) {
		return await $api.get('/control-panel/audit/', { params })
	}

	static async getEvent(eventId) {
		return await $api.get(`/control-panel/audit/${eventId}`)
	}
}
