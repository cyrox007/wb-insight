import $api from ".";

export default class AccountLifecycleService {
    static async cancelSubscription(reason = null) {
        return await $api.post('/account/subscription/cancel', { reason })
    }

    static async undoSubscriptionCancellation() {
        return await $api.delete('/account/subscription/cancel')
    }

    static async requestEmailChange(email) {
        return await $api.post('/account/email/change-request', { email })
    }

    static async cancelEmailChange() {
        return await $api.delete('/account/email/change-request')
    }

    static async deactivateAccount(reason = null) {
        return await $api.post('/account/deactivate', { reason })
    }
}
