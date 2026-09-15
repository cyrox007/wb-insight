import $api from '..'

export default class FinanceService {
  static async get_finance(params = {}) {
    return await $api.get('/dashboard/finance/', { params })
  }
}
