import $api from "..";

export default class TariffService {
    static async createPayment(tariff_code, idempotencyKey = null, legalConsents = []) {
        const headers = idempotencyKey
            ? { 'Idempotency-Key': idempotencyKey }
            : {};
        return $api.post('/billing/create-payment', {
            tariff_code: tariff_code,
            legal_consents: legalConsents
        }, { headers });
    }

    // Backward-compatible alias while callers migrate to createPayment().
    static async paymetTariff(tariff_code, idempotencyKey = null, legalConsents = []) {
        return this.createPayment(tariff_code, idempotencyKey, legalConsents);
    }
}
