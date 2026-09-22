import axios from "axios";
import {
    clearAccessToken,
    getAccessToken,
    purgeLegacyPersistentAuth,
    setAccessToken,
} from '@/security/session';

// В рабочем окружении systemd/nginx публикует серверную часть под /api.
// Локальная разработка через Vite использует прямой порт серверной части,
// при этом VITE_API_BASE_URL можно явно переопределить для Docker и нестандартных развёртываний.
const defaultApiBaseURL = import.meta.env.PROD ? '/api' : 'http://localhost:9000';

const resolveApiBaseURL = () => {
    const configuredBaseURL = (import.meta.env.VITE_API_BASE_URL || '').trim();
    if (!configuredBaseURL) return defaultApiBaseURL;

    if (import.meta.env.PROD && typeof window !== 'undefined') {
        try {
            const configuredURL = new URL(configuredBaseURL, window.location.href);
            if (configuredURL.origin !== window.location.origin) {
                console.warn(
                    'В рабочем окружении отклонён VITE_API_BASE_URL с другим источником; используется /api текущего сайта.',
                );
                return '/api';
            }
        } catch {
            console.warn(
                'В рабочем окружении отклонён некорректный VITE_API_BASE_URL; используется /api текущего сайта.',
            );
            return '/api';
        }
    }

    return configuredBaseURL;
};

const apiBaseURL = resolveApiBaseURL().replace(/\/$/, '');

const $api = axios.create({
    withCredentials: true,
    baseURL: apiBaseURL,
});

let refreshPromise = null;

const ACCOUNT_SCOPED_ENDPOINTS = new Set([
    '/dashboard/',
    '/dashboard/charts',
    '/dashboard/sync-status',
    '/dashboard/plan',
    '/dashboard/ads',
    '/dashboard/ads/',
    '/dashboard/unity',
    '/dashboard/unity/',
    '/dashboard/stocks',
    '/dashboard/stocks/',
    '/dashboard/prices',
    '/dashboard/prices/',
    '/dashboard/finance',
    '/dashboard/finance/',
]);

const clearClientSession = () => {
    clearAccessToken();
    purgeLegacyPersistentAuth();
    localStorage.removeItem('redirectPath');
};

export const refreshSessionRequest = async () => {
    const response = await axios.post(
        `${apiBaseURL}/auth/refresh`,
        {},
        { withCredentials: true },
    );
    const accessToken = response.data?.access_token;
    if (!accessToken) {
        throw new Error('Ответ обновления сессии не содержит access_token');
    }
    setAccessToken(accessToken);
    return response;
};

const refreshAccessToken = async () => {
    if (!refreshPromise) {
        refreshPromise = refreshSessionRequest().finally(() => {
            refreshPromise = null;
        });
    }
    return refreshPromise;
};

$api.interceptors.request.use((config) => {
    const accessToken = getAccessToken();
    if (accessToken) {
        config.headers.Authorization = `Bearer ${accessToken}`;
    }

    const requestPath = (config.url || '').split('?')[0];
    const selectedTokenId = localStorage.getItem('wb-dashboard-token-id');
    if (
        selectedTokenId &&
        ACCOUNT_SCOPED_ENDPOINTS.has(requestPath) &&
        !config.params?.token_id
    ) {
        config.params = { ...(config.params || {}), token_id: selectedTokenId };
    }

    return config;
}, (error) => Promise.reject(error));

$api.interceptors.response.use(
    (response) => response,
    async (error) => {
        const originalRequest = error.config;
        const requestPath = (originalRequest?.url || '').split('?')[0];

        if (
            error.response?.status === 401 &&
            originalRequest &&
            !originalRequest._isRetry &&
            requestPath !== '/auth/refresh'
        ) {
            originalRequest._isRetry = true;
            try {
                const refreshResponse = await refreshAccessToken();
                const accessToken = refreshResponse.data.access_token;
                originalRequest.headers = originalRequest.headers || {};
                originalRequest.headers.Authorization = `Bearer ${accessToken}`;
                return $api(originalRequest);
            } catch (refreshError) {
                clearClientSession();
                if (window.location.pathname !== '/') {
                    window.location.assign('/');
                }
                return Promise.reject(refreshError);
            }
        }

        if (error.response?.status === 403) {
            const forbiddenMessage =
                error.response.data?.error?.message ||
                error.response.data?.message ||
                'Недостаточно прав для выполнения действия';
            console.warn('Доступ запрещен:', forbiddenMessage);
            return Promise.reject(error);
        }

        if (error.response?.status === 400) {
            console.warn('Ошибка валидации (400):', error.response.data);
        }

        return Promise.reject(error);
    }
);

purgeLegacyPersistentAuth();

export { clearClientSession, setAccessToken };
export default $api;
