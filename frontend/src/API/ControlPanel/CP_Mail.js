import $api from '..'

export default class CP_Mail {
	static async getMeta() {
		return await $api.get('/control-panel/mail/meta')
	}

	static async getGateway() {
		return await $api.get('/control-panel/mail/gateway')
	}

	static async updateGateway(payload) {
		return await $api.put('/control-panel/mail/gateway', payload)
	}

	static async testGateway(email) {
		return await $api.post('/control-panel/mail/gateway/test', { email })
	}

	static async previewAudience(segment) {
		return await $api.post('/control-panel/mail/audience/preview', { segment })
	}

	static async getCampaigns(params = {}) {
		return await $api.get('/control-panel/mail/campaigns', { params })
	}

	static async getCampaign(id) {
		return await $api.get(`/control-panel/mail/campaigns/${id}`)
	}

	static async createCampaign(payload) {
		return await $api.post('/control-panel/mail/campaigns', payload)
	}

	static async updateCampaign(id, payload) {
		return await $api.put(`/control-panel/mail/campaigns/${id}`, payload)
	}

	static async previewCampaign(id) {
		return await $api.post(`/control-panel/mail/campaigns/${id}/preview`)
	}

	static async testSend(id, email) {
		return await $api.post(`/control-panel/mail/campaigns/${id}/test-send`, { email })
	}

	static async schedule(id, scheduledAt) {
		return await $api.post(`/control-panel/mail/campaigns/${id}/schedule`, { scheduled_at: scheduledAt })
	}

	static async launch(id) {
		return await $api.post(`/control-panel/mail/campaigns/${id}/launch`)
	}

	static async cancel(id) {
		return await $api.post(`/control-panel/mail/campaigns/${id}/cancel`)
	}

	static async getMessages(id, params = {}) {
		return await $api.get(`/control-panel/mail/campaigns/${id}/messages`, { params })
	}
}
