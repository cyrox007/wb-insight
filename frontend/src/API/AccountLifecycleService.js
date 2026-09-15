import $api from ".";

export default class AccountLifecycleService {
    static async cancelSubscription(reason = null) {
        return await $api.post('/account/subscription/cancel', { reason })
    }

    static async undoSubscriptionCancellation() {
        return await $api.delete('/account/subscription/cancel')
    }

    static async deactivateAccount(reason = null) {
        return await $api.post('/account/deactivate', { reason })
    }
}
