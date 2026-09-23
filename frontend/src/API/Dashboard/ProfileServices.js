import $api from "..";

export default class ProfileServices {
    static async getProfile() {
        return await $api.get('/dashboard/profile/');
    }

    static async updateProfile(data) {
        return await $api.put('/dashboard/profile/', data);
    }

    static async requestEmailChange(email) {
        return await $api.post('/dashboard/profile/email-change/request', { email });
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

    static async get_user_tokens_by_id(id) {
        return await $api.get(`/dashboard/profile/tokens/${id}`);
    }

    static async delete_user_token(id) {
        return await $api.delete(`/dashboard/profile/token/${id}`)
    }

    static async add_user_token(data) {
        return await $api.post(`/dashboard/tokens`, data);
    }
}
