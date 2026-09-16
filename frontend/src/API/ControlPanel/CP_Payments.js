import $api from '..'

export default class CP_Payments {
	static async getProviders() {
		return await $api.get('/control-panel/payments/providers')
	}

	static async updateProvider(provider, mode, payload) {
		return await $api.put(`/control-panel/payments/providers/${provider}/${mode}`, payload)
	}

	static async getJournal(params = {}) {
		return await $api.get('/control-panel/payments/journal', { params })
	}

	static async getPayment(paymentId) {
		return await $api.get(`/control-panel/payments/journal/${paymentId}`)
	}
}
