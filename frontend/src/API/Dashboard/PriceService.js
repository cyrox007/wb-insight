import $api from "..";

export default class PriceService {
    static async get_prices() {
        return await $api.get('/dashboard/prices/');
    }
}
