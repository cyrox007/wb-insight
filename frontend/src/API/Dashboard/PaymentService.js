import $api from "..";

export default class PaymentService {
    static async getPayment(paymentId) {
        return $api.get(`/billing/payments/${paymentId}`);
    }

    static async confirmPayment(paymentId) {
        return $api.post(`/billing/payments/${paymentId}/confirm`);
    }

    static async payNow(payment_id) {
        return $api.post("/billing/pay-now", { payment_id });
    }
}
