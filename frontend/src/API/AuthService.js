import $api from ".";

export default class AuthService {
    static async login(email, password) {
        return $api.post('/auth/login', {
            email: email,
            password: password
        })
    }
}