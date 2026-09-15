import $api from '.'

export default class LegalService {
    static async requirements(context) {
        return await $api.get(`/legal/requirements/${context}`)
    }

    static async document(code) {
        return await $api.get(`/legal/documents/${code}`)
    }
}
