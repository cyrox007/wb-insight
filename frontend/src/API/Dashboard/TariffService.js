import $api from "..";

export default class TariffService {
    static async createPayment(tariff_code) {
        return $api.post('/billing/create-payment', {
            tariff_code: tariff_code
        });
    }

    // Backward-compatible alias while callers migrate to createPayment().
    static async paymetTariff(tariff_code) {
        return this.createPayment(tariff_code);
    }
}
