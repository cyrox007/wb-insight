import axios from "axios";

const $api = axios.create({
    withCredentials: true,
    baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:9000',
});

let isRefreshing = false;
let failedQueue = [];

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
]);

const clearLocalSession = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user');
    localStorage.removeItem('redirectPath');
    localStorage.removeItem('wb-dashboard-token-id');
};

const processQueue = (error = null) => {
    failedQueue.forEach(({ resolve, reject }) => {
        if (error) reject(error);
        else resolve();
    });
    failedQueue = [];
};

$api.interceptors.request.use((config) => {
    const accessToken = localStorage.getItem('access_token');
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

        if (error.response?.status === 401 && originalRequest && !originalRequest._isRetry) {
            if (!isRefreshing) {
                isRefreshing = true;
                originalRequest._isRetry = true;

                try {
                    const refreshResponse = await axios.post(
                        `${$api.defaults.baseURL}/auth/refresh`,
                        {},
                        { withCredentials: true },
                    );
                    const { access_token } = refreshResponse.data;

                    if (!access_token) {
                        throw new Error('Refresh response does not contain access_token');
                    }

                    localStorage.setItem('access_token', access_token);
                    originalRequest.headers = originalRequest.headers || {};
                    originalRequest.headers.Authorization = `Bearer ${access_token}`;

                    processQueue();
                    return $api(originalRequest);
                } catch (refreshError) {
                    processQueue(refreshError);
                    clearLocalSession();
                    window.location.href = '/';
                    return Promise.reject(refreshError);
                } finally {
                    isRefreshing = false;
                }
            }

            return new Promise((resolve, reject) => {
                failedQueue.push({ resolve, reject });
            }).then(() => $api(originalRequest));
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

export default $api;
