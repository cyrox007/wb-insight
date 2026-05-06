import $api from "..";

export default class AdsService {
    static async get_ads_stats(params = {}) {
        return await $api.get("/dashboard/ads/", { params });
    }
}
