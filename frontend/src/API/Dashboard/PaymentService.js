import $api from "..";

export default class PaymentService {

    static async payNow(payment_id) {
        return await $api.post("/billing/pay-now", {payment_id});
    }
}