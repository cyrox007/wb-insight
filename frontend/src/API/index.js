import axios from "axios";
import {
    clearAccessToken,
    getAccessToken,
    purgeLegacyPersistentAuth,
    setAccessToken,
} from '@/security/session';

// Systemd/nginx production exposes the backend under /api. Keep local Vite
// development on the direct backend port, while still allowing an explicit
// VITE_API_BASE_URL override for Docker/custom deployments.
const defaultApiBaseURL = import.meta.env.PROD ? '/api' : 'http://localhost:9000';
const apiBaseURL = (import.meta.env.VITE_API_BASE_URL || defaultApiBaseURL).replace(/\/$/, '');

const $api = axios.create({
    withCredentials: true,
    baseURL: apiBaseURL,
});

let refreshPromise = null;

const ACCOUNT_SCOPED_ENDPOINTS = new Set([
    '/dashboard/',
    '/dashboard/charts',
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
        throw new Error('Refresh response does not contain access_token');
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
            console.warn(
                'Доступ запрещен:',
                error.response.data?.message || 'Недостаточно прав для выполнения действия',
            );
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
