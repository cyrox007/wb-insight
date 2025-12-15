import $api from ".";

export default class AuthService {
    static async login(email, password) {
        return await $api.post('/auth/login', {
            email: email,
            password: password
        })
    }
}