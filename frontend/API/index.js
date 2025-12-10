import axios from "axios";

const $api = axios.create({
    withCredentials: true, // Включаем отправку кук
    baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:9000', // Базовый URL вашего API
});