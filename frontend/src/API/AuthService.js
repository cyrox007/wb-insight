import $api, { invalidateSessionRefresh, refreshSessionRequest } from ".";
import LegalService from "@/API/LegalService";

export default class AuthService {
    static async login(email, password) {
        return await $api.post('/auth/login', { email, password })
    }

    static async refresh() {
        return await refreshSessionRequest()
    }

    static async logout() {
        invalidateSessionRefresh()
        return await $api.post('/auth/logout')
    }

    static async requestPasswordReset(email) {
        return await $api.post('/auth/password-reset/request', { email })
    }

    static async confirmPasswordReset(token, newPassword) {
        return await $api.post('/auth/password-reset/confirm', { token, new_password: newPassword })
    }

    static async confirmEmail(token) {
        return await $api.post('/auth/email-verification/confirm', { token })
    }

    static async resendEmailVerification(email) {
        return await $api.post('/auth/email-verification/resend', { email })
    }

    static async checkEmail(email) {
        return await $api.post('/auth/check-email', { email });
    }

    static async checkPhone(phone) {
        return await $api.post('/auth/check-phone', { phone });
    }

    static async checkInn(inn) {
        return await $api.post('/auth/check-inn', { inn })
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
            .map((doc) => ({ code: doc.code, version: doc.version, sha256: doc.sha256, accepted: true }));

        const response = await $api.post('/auth/registration', {
            registrationData: { ...registrationData, legal_consents: legalConsents }
        })
        if (response.data?.status === 'success' && response.data?.email_verification_required) {
            sessionStorage.setItem('pendingVerificationEmail', response.data.email || registrationData.email || '')
            window.location.assign('/verify-email')
        }
        return response
    }
}
