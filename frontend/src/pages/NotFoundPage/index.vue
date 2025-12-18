<template>
	<div class="not-found-container">
		<div class="not-found-content">
			<!-- Анимированный номер 404 -->
			<div class="error-number">
				<span class="digit">4</span>
				<span class="digit zero">0</span>
				<span class="digit">4</span>
			</div>

			<!-- Иконка или иллюстрация -->
			<div class="error-illustration">
				<svg class="error-icon" viewBox="0 0 200 200" fill="none">
					<circle cx="100" cy="100" r="80" stroke="var(--secondary-color)" stroke-width="4" />
					<path d="M60,60 L140,140" stroke="var(--accent-color)" stroke-width="4" stroke-linecap="round" />
					<path d="M140,60 L60,140" stroke="var(--accent-color)" stroke-width="4" stroke-linecap="round" />
					<circle cx="100" cy="100" r="60" stroke="var(--border-color)" stroke-width="2"
						stroke-dasharray="5,5" />
				</svg>
			</div>

			<!-- Сообщение об ошибке -->
			<div class="error-message">
				<h1>Страница не найдена</h1>
				<p class="subtitle">
					Запрашиваемая страница не существует или была перемещена
				</p>
				<p class="description">
					Возможно, вы ввели неправильный адрес или страница была удалена.
					Проверьте правильность URL или вернитесь на главную.
				</p>
			</div>

			<!-- Действия -->
			<div class="actions">
				<router-link :to="{ name: 'home' }" class="btn btn-primary">
					<svg class="btn-icon" fill="currentColor" viewBox="0 0 20 20">
						<path
							d="M10.707 2.293a1 1 0 00-1.414 0l-7 7a1 1 0 001.414 1.414L4 10.414V17a1 1 0 001 1h2a1 1 0 001-1v-2a1 1 0 011-1h2a1 1 0 011 1v2a1 1 0 001 1h2a1 1 0 001-1v-6.586l.293.293a1 1 0 001.414-1.414l-7-7z" />
					</svg>
					На главную
				</router-link>

				<router-link v-if="isAuthenticated" :to="{ name: 'dashboard.home' }" class="btn btn-secondary">
					<svg class="btn-icon" fill="currentColor" viewBox="0 0 20 20">
						<path
							d="M2 11a1 1 0 011-1h2a1 1 0 011 1v5a1 1 0 01-1 1H3a1 1 0 01-1-1v-5zM8 7a1 1 0 011-1h2a1 1 0 011 1v9a1 1 0 01-1 1H9a1 1 0 01-1-1V7zM14 4a1 1 0 011-1h2a1 1 0 011 1v12a1 1 0 01-1 1h-2a1 1 0 01-1-1V4z" />
					</svg>
					В дашборд
				</router-link>

				<button @click="goBack" class="btn btn-outline">
					<svg class="btn-icon" fill="currentColor" viewBox="0 0 20 20">
						<path fill-rule="evenodd"
							d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L5.414 9H17a1 1 0 110 2H5.414l4.293 4.293a1 1 0 010 1.414z"
							clip-rule="evenodd" />
					</svg>
					Вернуться назад
				</button>
			</div>

			<!-- Дополнительная информация -->
			<div class="additional-info">
				<div class="info-card">
					<svg class="info-icon" fill="currentColor" viewBox="0 0 20 20">
						<path fill-rule="evenodd"
							d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
							clip-rule="evenodd" />
					</svg>
					<p>Если проблема повторяется, свяжитесь с поддержкой</p>
				</div>

				<div class="info-card">
					<svg class="info-icon" fill="currentColor" viewBox="0 0 20 20">
						<path d="M2.003 5.884L10 9.882l7.997-3.998A2 2 0 0016 4H4a2 2 0 00-1.997 1.884z" />
						<path d="M18 8.118l-8 4-8-4V14a2 2 0 002 2h12a2 2 0 002-2V8.118z" />
					</svg>
					<p>support@wildberries-dashboard.com</p>
				</div>
			</div>

			<!-- Ссылка на статус сервиса -->
			<!-- <div class="status-link">
				<router-link :to="{ name: 'status' }">
					<svg class="status-icon" fill="currentColor" viewBox="0 0 20 20">
						<path fill-rule="evenodd"
							d="M5.05 3.636a1 1 0 010 1.414 7 7 0 000 9.9 1 1 0 11-1.414 1.414 9 9 0 010-12.728 1 1 0 011.414 0zm9.9 0a1 1 0 011.414 0 9 9 0 010 12.728 1 1 0 11-1.414-1.414 7 7 0 000-9.9 1 1 0 010-1.414zM7.879 6.464a1 1 0 010 1.414 3 3 0 000 4.243 1 1 0 11-1.415 1.414 5 5 0 010-7.07 1 1 0 011.415 0zm4.242 0a1 1 0 011.415 0 5 5 0 010 7.072 1 1 0 01-1.415-1.415 3 3 0 000-4.242 1 1 0 010-1.415zM10 9a1 1 0 011 1v.01a1 1 0 11-2 0V10a1 1 0 011-1z"
							clip-rule="evenodd" />
					</svg>
					Проверить статус сервиса
				</router-link>
			</div> -->
		</div>

		<!-- Футер -->
		<footer class="not-found-footer">
			<p>© 2025 Wildberries Dashboard. Все права защищены.</p>
			<p>Ошибка 404 • Страница не найдена</p>
		</footer>
	</div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const errorPath = ref('')

// Проверка авторизации (замените на свою логику)
const isAuthenticated = computed(() => {
	return localStorage.getItem('auth_token') !== null
})

onMounted(() => {
	// Можно сохранить путь, на который пытались перейти
	errorPath.value = window.location.pathname
	console.warn(`Страница не найдена: ${errorPath.value}`)
})

const goBack = () => {
	if (window.history.length > 1) {
		router.go(-1)
	} else {
		router.push({ name: 'home' })
	}
}

// Анимация для цифр
onMounted(() => {
	const digits = document.querySelectorAll('.digit')
	digits.forEach((digit, index) => {
		setTimeout(() => {
			digit.style.opacity = '1'
			digit.style.transform = 'translateY(0)'
		}, index * 200)
	})
})
</script>

<style scoped>
.not-found-container {
	min-height: 100vh;
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	background: linear-gradient(135deg, var(--dark-bg) 0%, var(--medium-bg) 100%);
	color: var(--text-color);
	padding: 2rem;
	position: relative;
	overflow: hidden;
}

.not-found-container::before {
	content: '';
	position: absolute;
	width: 300%;
	height: 300%;
	background: radial-gradient(circle, transparent 20%, var(--dark-bg) 70%);
	animation: pulse 15s infinite linear;
}

@keyframes pulse {
	0% {
		transform: rotate(0deg) scale(1);
	}

	50% {
		transform: rotate(180deg) scale(1.1);
	}

	100% {
		transform: rotate(360deg) scale(1);
	}
}

.not-found-content {
	position: relative;
	z-index: 1;
	max-width: 800px;
	width: 100%;
	text-align: center;
	padding: 3rem;
	background: rgba(37, 37, 37, 0.8);
	backdrop-filter: blur(10px);
	border-radius: 20px;
	border: 1px solid var(--border-color);
	box-shadow:
		0 20px 40px rgba(0, 0, 0, 0.5),
		inset 0 1px 0 rgba(255, 255, 255, 0.1);
}

/* Error Number */
.error-number {
	display: flex;
	justify-content: center;
	gap: 1.5rem;
	margin-bottom: 2rem;
}

.digit {
	font-size: 8rem;
	font-weight: 900;
	color: var(--secondary-color);
	opacity: 0;
	transform: translateY(-50px);
	transition: all 0.6s cubic-bezier(0.34, 1.56, 0.64, 1);
	text-shadow:
		0 0 30px rgba(52, 152, 219, 0.5),
		0 10px 20px rgba(0, 0, 0, 0.3);
}

.digit.zero {
	color: var(--accent-color);
	animation: float 3s ease-in-out infinite;
}

@keyframes float {

	0%,
	100% {
		transform: translateY(0) rotate(0deg);
	}

	50% {
		transform: translateY(-20px) rotate(5deg);
	}
}

/* Error Illustration */
.error-illustration {
	margin: 2rem auto;
	max-width: 200px;
	opacity: 0.8;
}

.error-icon {
	width: 100%;
	height: auto;
	filter: drop-shadow(0 5px 15px rgba(0, 0, 0, 0.3));
	animation: rotate 20s linear infinite;
}

@keyframes rotate {
	from {
		transform: rotate(0deg);
	}

	to {
		transform: rotate(360deg);
	}
}

/* Error Message */
.error-message {
	margin: 2rem 0 3rem;
}

.error-message h1 {
	font-size: 2.5rem;
	margin-bottom: 1rem;
	background: linear-gradient(45deg, var(--text-color), var(--secondary-color));
	-webkit-background-clip: text;
	-webkit-text-fill-color: transparent;
	background-clip: text;
}

.subtitle {
	font-size: 1.2rem;
	color: #aaa;
	margin-bottom: 1rem;
}

.description {
	color: #888;
	line-height: 1.6;
	max-width: 600px;
	margin: 0 auto;
}

/* Actions */
.actions {
	display: flex;
	gap: 1rem;
	justify-content: center;
	flex-wrap: wrap;
	margin: 3rem 0;
}

.btn {
	padding: 0.75rem 1.5rem;
	border-radius: 8px;
	font-weight: 500;
	text-decoration: none;
	display: inline-flex;
	align-items: center;
	gap: 0.5rem;
	transition: all 0.3s ease;
	border: none;
	cursor: pointer;
	font-size: 1rem;
}

.btn-primary {
	background: linear-gradient(45deg, var(--secondary-color), #2980b9);
	color: white;
	box-shadow: 0 4px 15px rgba(52, 152, 219, 0.3);
}

.btn-primary:hover {
	transform: translateY(-2px);
	box-shadow: 0 6px 20px rgba(52, 152, 219, 0.4);
}

.btn-secondary {
	background: var(--medium-bg);
	color: var(--text-color);
	border: 1px solid var(--border-color);
}

.btn-secondary:hover {
	background: var(--hover-bg);
	transform: translateY(-2px);
}

.btn-outline {
	background: transparent;
	color: var(--text-color);
	border: 1px solid var(--border-color);
}

.btn-outline:hover {
	background: rgba(255, 255, 255, 0.05);
	transform: translateY(-2px);
}

.btn-icon {
	width: 20px;
	height: 20px;
}

/* Additional Info */
.additional-info {
	display: grid;
	grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
	gap: 1rem;
	margin: 3rem 0;
}

.info-card {
	background: var(--card-bg);
	padding: 1.5rem;
	border-radius: 10px;
	border-left: 4px solid var(--info-color);
	display: flex;
	align-items: center;
	gap: 1rem;
	text-align: left;
	transition: var(--transition);
}

.info-card:hover {
	transform: translateY(-5px);
	background: var(--hover-bg);
}

.info-icon {
	width: 24px;
	height: 24px;
	color: var(--info-color);
	flex-shrink: 0;
}

.info-card p {
	margin: 0;
	color: #aaa;
	font-size: 0.9rem;
}

/* Status Link */
.status-link {
	margin: 2rem 0;
}

.status-link a {
	color: var(--warning-color);
	text-decoration: none;
	display: inline-flex;
	align-items: center;
	gap: 0.5rem;
	transition: var(--transition);
}

.status-link a:hover {
	color: #f1c40f;
	text-decoration: underline;
}

.status-icon {
	width: 20px;
	height: 20px;
}

/* Footer */
.not-found-footer {
	margin-top: 3rem;
	position: relative;
	z-index: 1;
	text-align: center;
	color: #666;
	font-size: 0.9rem;
	padding-top: 2rem;
	border-top: 1px solid var(--border-color);
	width: 100%;
	max-width: 800px;
}

.not-found-footer p {
	margin: 0.5rem 0;
}

/* Responsive */
@media (max-width: 768px) {
	.not-found-content {
		padding: 2rem;
		margin: 1rem;
	}

	.digit {
		font-size: 5rem;
	}

	.error-message h1 {
		font-size: 2rem;
	}

	.actions {
		flex-direction: column;
		align-items: center;
	}

	.btn {
		width: 100%;
		max-width: 300px;
		justify-content: center;
	}

	.additional-info {
		grid-template-columns: 1fr;
	}
}

@media (max-width: 480px) {
	.digit {
		font-size: 4rem;
	}

	.error-number {
		gap: 1rem;
	}

	.error-message h1 {
		font-size: 1.8rem;
	}
}
</style>