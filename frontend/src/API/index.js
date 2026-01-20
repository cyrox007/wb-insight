import axios from "axios";

const $api = axios.create({
    withCredentials: true, // Включаем отправку кук
    baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:9000', // Базовый URL вашего API
});

// Перехватчик запросов: добавляем токен в заголовки
$api.interceptors.request.use((config) => {
    const accessToken = localStorage.getItem('access_token');
    if (accessToken) {
        config.headers.Authorization = `Bearer ${accessToken}`;
        config.headers['X-User-UID'] = JSON.parse(localStorage.getItem('user')).id
    }
    return config;
}, (error) => {
    return Promise.reject(error);
});

// Перехватчик ответов: обработка ошибок
$api.interceptors.response.use(
    (response) => response,
    async (error) => {
        const originalRequest = error.config;

        // Обработка ошибки 401 Unauthorized
        if (error.response?.status === 401 && !originalRequest._isRetry) {
            if (!isRefreshing) {
                isRefreshing = true;
                originalRequest._isRetry = true;

                try {
                    // Обновляем токен
                    const refreshResponse = await axios.get(`${$api.defaults.baseURL}/refresh`, {
                        withCredentials: true,
                    });
                    const { status, access_token } = refreshResponse.data;
                    console.log(access_token);
                    
                    // Сохраняем новый access_token
                    localStorage.setItem('access_token', access_token);

                    // Устанавливаем новый токен в заголовки
                    originalRequest.headers.Authorization = `Bearer ${access_token}`;

                    // Повторяем все запросы из очереди
                    processQueue();

                    // Повторяем исходный запрос и возвращаем его результат
                    return $api(originalRequest);
                } catch (refreshError) {
                    // Если обновление токена не удалось, очищаем данные и перенаправляем на страницу входа
                    processQueue(refreshError);
                    localStorage.clear();
                    store.dispatch('clearUser');
                    window.location.href = '/login';
                    return Promise.reject(refreshError);
                } finally {
                    isRefreshing = false;
                }
            } else {
                // Добавляем запрос в очередь на повторение
                return new Promise((resolve, reject) => {
                    failedQueue.push((err) => {
                        if (err) {
                            reject(err);
                        } else {
                            resolve($api(originalRequest));
                        }
                    });
                });
            }
        }

        // Обработка ошибки 403 Forbidden
        if (error.response?.status === 403) {
            console.error('Доступ запрещен: токен недействителен или удален.');

            // Очищаем данные аутентификации
            localStorage.clear();
            store.dispatch('clearUser');
            
            // Перенаправляем пользователя на страницу входа
            const allowedPaths = ['/login', '/registration'];

            if (!allowedPaths.some(path => window.location.pathname.includes(path))) {
                window.location.href = '/login';
            }

            // Прерываем выполнение
            throw error;
        }

        // Обработка других ошибок
        if (error.response?.status === 400) {
			console.warn('Ошибка валидации (400):', error.response.data);
			// Просто пропускаем ошибку дальше — компонент сам обработает
		}

        // Пробрасываем ошибку дальше
        return Promise.reject(error);
    }
);

export default $api;