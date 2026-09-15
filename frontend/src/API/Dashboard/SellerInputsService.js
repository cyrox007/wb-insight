import $api from '..'

export default class SellerInputsService {
    static async getCostProducts(params = {}) {
        return await $api.get('/cost-prices/products', { params })
    }

    static async saveCostPrices(items) {
        return await $api.post('/cost-prices/batch', { items })
    }

    static async uploadCostPrices(file) {
        const formData = new FormData()
        formData.append('file', file)
        return await $api.post('/cost-prices/upload', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
        })
    }

    static async deleteCostPrice(nmId) {
        return await $api.delete(`/cost-prices/${nmId}`)
    }

    static async getExpenses(params = {}) {
        return await $api.get('/dashboard/expenses/', { params })
    }

    static async createExpense(data) {
        return await $api.post('/dashboard/expenses/', data)
    }

    static async updateExpense(id, data) {
        return await $api.put(`/dashboard/expenses/${id}`, data)
    }

    static async deleteExpense(id) {
        return await $api.delete(`/dashboard/expenses/${id}`)
    }
}
