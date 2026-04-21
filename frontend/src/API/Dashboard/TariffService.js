import $api from "..";

export default class TariffService {
    static async paymetTariff(tariff_code) {
        return $api.post('/billing/create-payment', {
            tariff_code: tariff_code
        })
    }
}