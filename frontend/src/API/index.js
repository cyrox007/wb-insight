import axios from "axios";

const $api = axios.create({
    withCredentials: true, // Включаем отправку кук
    baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:9000', // Базовый URL вашего API
});

let isRefreshing = false;
let failedQueue = [];

const processQueue = (error = null) => {
	failedQueue.forEach(({ resolve, reject }) => {
		if (error) {
			reject(error);
		} else {
			resolve();
		}
	});
	failedQueue = [];
};

// Перехватчик запросов: добавляем токен в заголовки
$api.interceptors.request.use((config) => {
    const accessToken = localStorage.getItem('access_token');
    if (accessToken) {
        config.headers.Authorization = `Bearer ${accessToken}`;
        const userStr = localStorage.getItem('user');
        if (userStr) {
            const user = JSON.parse(userStr);
            if (user && user.id) {
                config.headers['X-User-UID'] = user.id;
            }
        }
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
                    const refreshResponse = await axios.get(`${$api.defaults.baseURL}/auth/refresh`, {
                        withCredentials: true,
                    });
                    const { status, access_token } = refreshResponse.data;
                    //console.log(access_token);
                    
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
                    localStorage.removeItem('access_token');
                    localStorage.removeItem('user');
                    // И удаляем куки, если они используются
                    document.cookie.split(";").forEach((c) => {
                        document.cookie = c.replace(/^ +/, "").replace(/=.*/, "=;expires=" + new Date().toUTCString() + ";path=/");
                    });
                    window.location.href = '/login';
                    return Promise.reject(refreshError);
                } finally {
                    isRefreshing = false;
                }
            } else {
                // Добавляем запрос в очередь на повторение
                return new Promise((resolve, reject) => {
                    failedQueue.push({ resolve, reject }); // ← ПРАВИЛЬНО: объект
                }).then(() => {
                    return $api(originalRequest);
                });
            }
        }

        // Обработка ошибки 403 Forbidden
        if (error.response?.status === 403) {
            console.warn('Доступ запрещен:', error.response.data?.message || 'Недостаточно прав для выполнения действия');

            // НЕ делаем логаут! 403 может означать просто отсутствие прав на конкретное действие
            // (например, попытка удалить чужой токен), а не невалидность сессии

            // Просто пробрасываем ошибку дальше — компонент сам решит как обработать
            return Promise.reject(error);
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