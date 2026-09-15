import $api, { refreshSessionRequest } from ".";
import LegalService from "@/API/LegalService";

export default class AuthService {
    static async login(email, password) {
        return await $api.post('/auth/login', {
            email: email,
            password: password
        })
    }

    static async refresh() {
        return await refreshSessionRequest()
    }

    static async logout() {
        return await $api.post('/auth/logout')
    }

    static async checkEmail(email) {
        return await $api.post('/auth/check-email', {
            email: email
        });
    }

    static async checkPhone(phone) {
        return await $api.post('/auth/check-phone', {
            phone: phone
        });
    }

    static async checkInn(inn) {
        return await $api.post('/auth/check-inn', {
            inn: inn
        })
    }

    static async registration(registrationData) {
        const context = registrationData.entity_type === 'legal_entity'
            ? 'registration_legal'
            : 'registration';
        const requirements = await LegalService.requirements(context);
        const documents = requirements.data?.documents || [];
        const accepted = {
            terms: registrationData.agree_terms === true,
            privacy: registrationData.agree_privacy === true,
            personal_data: registrationData.agree_data_processing === true
        };
        const legalConsents = documents
            .filter((doc) => accepted[doc.code] === true)
            .map((doc) => ({
                code: doc.code,
                version: doc.version,
                sha256: doc.sha256,
                accepted: true
            }));

        return await $api.post('/auth/registration', {
            registrationData: {
                ...registrationData,
                legal_consents: legalConsents
            }
        })
    }
}
