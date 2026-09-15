import $api from "..";

export default class InventoryService {
    static async get_inventory() {
        return await $api.get('/dashboard/stocks/');
    }
}
