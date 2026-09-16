import $api from '..'

export default class CP_Mail {
	static async getCampaigns(params = {}) {
		return await $api.get('/control-panel/mail/campaigns', { params })
	}

	static async getCampaign(id) {
		return await $api.get(`/control-panel/mail/campaigns/${id}`)
	}

	static async createCampaign(payload) {
		return await $api.post('/control-panel/mail/campaigns', payload)
	}

	static async previewCampaign(id) {
		return await $api.post(`/control-panel/mail/campaigns/${id}/preview`)
	}

	static async testSend(id, email) {
		return await $api.post(`/control-panel/mail/campaigns/${id}/test-send`, { email })
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
