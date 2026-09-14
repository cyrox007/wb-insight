import $api from ".";

export default class AuthService {
    static async login(email, password) {
        return await $api.post('/auth/login', {
            email: email,
            password: password
        })
    }

    static async refresh() {
        return await $api.post('/auth/refresh')
    }

    static async logout() {
        return await $api.post('/auth/logout')
    }

    static async checkEmail(email) {
        return await $api.post('/auth/check-email', {
            email: email
        });
    }

    static async checkPhone(phone) {
        return await $api.post('/auth/check-phone', {
            phone: phone
        });
    }

    static async checkInn(inn) {
        return await $api.post('/auth/check-inn', {
            inn: inn
        })
    }

    static async registration(registrationData) {
        return await $api.post('/auth/registration', { registrationData: registrationData})
    }
}