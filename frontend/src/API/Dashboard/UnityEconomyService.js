import $api from "..";

export default class UnityEconomyService {
    static async get_unity_economy_table(params = {}) {
        return await $api.get('/dashboard/unity', { params })
    }
}
