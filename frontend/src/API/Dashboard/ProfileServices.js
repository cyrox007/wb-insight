import $api from "..";

export default class ProfileServices {
    static async getProfile() {
        return await $api.get('/dashboard/profile/');
    }

    static async checkTokenPermission(user_id, tariff_id) {
        return await $api.get(`/dashboard/profile/check-token-permission/${user_id}`, {
            params: {
                tariff_id: tariff_id
            }
        });
    }

    static async get_tariffs() {
        return await $api.get(`/dashboard/tariffs`);
    }
}