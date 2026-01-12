<template>
	<div class="dashboard-container">
		<div class="profile-card">
			<div class="profile-header">
				<div class="avatar-placeholder">
					<!-- Можно заменить на <img :src="user.avatar" /> при наличии -->
					<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
							d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
					</svg>
				</div>
				<div class="user-info">
					<h2 class="user-name">{{ user.name }}</h2>
					<p class="user-email">{{ user.email }}</p>
				</div>
			</div>

			<div class="">
				<button @click="showEditProfile = true" class="edit-btn">
					<svg class="edit-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
							d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
					</svg>
					Редактировать профиль
				</button>
			</div>
		</div>

		<div class="tokens-section">
			<div class="section-header">
				<h3>Токены продавца Wildberries</h3>
				<button @click="showAddTokenModal = true" class="add-token-btn">
					+ Добавить токен
				</button>
			</div>

			<div v-if="tokens.length === 0" class="empty-state">
				У вас пока нет токенов. Добавьте первый токен для доступа к данным Wildberries.
			</div>

			<ul v-else class="tokens-list">
				<li v-for="token in tokens" :key="token.id" class="token-item">
					<div class="token-content">
						<span class="token-masked">{{ maskToken(token.value) }}</span>
						<span class="token-meta">Добавлен: {{ formatDate(token.created_at) }}</span>
					</div>
					<div class="token-actions">
						<button @click="copyToken(token.value)" class="btn-icon" title="Скопировать">
							<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"
								stroke="currentColor" width="16" height="16">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
									d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
							</svg>
						</button>
						<button @click="deleteToken(token.id)" class="btn-icon delete-btn" title="Удалить">
							<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"
								stroke="currentColor" width="16" height="16">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
									d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M9 7h6" />
							</svg>
						</button>
					</div>
				</li>
			</ul>
		</div>
	</div>
</template>

<script setup>
import { ref } from 'vue'

const user = ref({
	name: 'Иван Петров',
	email: 'ivan@example.com'
})

const tokens = ref([
	/* { id: 1, value: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xxxxx', created_at: '2026-01-10T14:30:00' },
	{ id: 2, value: 'abc123def456ghi789jkl000mnopqrstu', created_at: '2026-01-12T09:15:00' } */
])

const showEditProfile = ref(false)
const showAddTokenModal = ref(false)

function maskToken(token) {
	if (token.length <= 8) return token
	return token.substring(0, 4) + '••••••' + token.slice(-4)
}

// Формат даты (простой вариант)
function formatDate(isoString) {
	const date = new Date(isoString)
	return date.toLocaleDateString('ru-RU', {
		year: 'numeric',
		month: 'short',
		day: 'numeric',
		hour: '2-digit',
		minute: '2-digit'
	})
}

// Имитация действий
function copyToken(token) {
	navigator.clipboard.writeText(token).then(() => {
		alert('Токен скопирован в буфер обмена')
	}).catch(() => {
		alert('Не удалось скопировать токен')
	})
}

function deleteToken(id) {
	if (confirm('Удалить токен? Это действие нельзя отменить.')) {
		tokens.value = tokens.value.filter(t => t.id !== id)
	}
}
</script>

<style scoped>
.dashboard-container {
	padding: 20px;
}

@media (max-width: 1023px) {
	.dashboard-container {
		grid-template-columns: 1fr;
		padding: 16px;
	}
}

.profile-card {
	display: flex;
	flex-direction: column;
	justify-content: space-between;
	width: 100%;
	padding: 24px;
	background-color: var(--card-bg);
	border: 1px solid var(--border-color);
	border-radius: 12px;
	box-shadow: var(--shadow);
	gap: 20px;
}

.profile-header {
	display: flex;
	align-items: center;
	gap: 16px;
}

.avatar-placeholder {
	width: 60px;
	height: 60px;
	border-radius: 50%;
	background-color: var(--medium-bg);
	display: flex;
	align-items: center;
	justify-content: center;
	color: var(--secondary-color);
}

.avatar-placeholder svg {
	width: 32px;
	height: 32px;
}

.user-info {
	display: flex;
	flex-direction: column;
}

.user-name {
	font-size: 1.4rem;
	font-weight: 600;
	color: var(--text-color);
	margin-bottom: 4px;
}

.user-email {
	font-size: 0.95rem;
	color: #aaa;
}

.edit-btn {
	display: inline-flex;
	align-items: center;
	gap: 8px;
	padding: 10px 16px;
	background-color: var(--secondary-color);
	color: white;
	border: none;
	border-radius: 6px;
	font-weight: 500;
	cursor: pointer;
	transition: var(--transition);
}

.edit-btn:hover {
	background-color: #2980b9;
	transform: translateY(-2px);
}

.edit-icon {
	width: 18px;
	height: 18px;
}

.tokens-section {
	background-color: var(--card-bg);
	border: 1px solid var(--border-color);
	border-radius: 12px;
	padding: 24px;
	box-shadow: var(--shadow);
	margin-top: 20px;
}

.section-header {
	display: flex;
	justify-content: space-between;
	align-items: center;
	margin-bottom: 16px;
}

.section-header h3 {
	font-size: 1.25rem;
	font-weight: 600;
	color: var(--text-color);
}

.add-token-btn {
	padding: 8px 16px;
	background-color: var(--success-color);
	color: white;
	border: none;
	border-radius: 6px;
	font-weight: 500;
	cursor: pointer;
	transition: var(--transition);
}

.add-token-btn:hover {
	background-color: #27ae60;
	transform: translateY(-1px);
}

.empty-state {
	color: #aaa;
	font-style: italic;
	text-align: center;
	padding: 20px;
}

.tokens-list {
	list-style: none;
	padding: 0;
	margin: 0;
}

.token-item {
	display: flex;
	justify-content: space-between;
	align-items: center;
	padding: 14px;
	background-color: var(--medium-bg);
	border-radius: 8px;
	margin-bottom: 10px;
}

.token-content {
	flex: 1;
}

.token-masked {
	font-family: monospace;
	font-size: 0.95rem;
	color: var(--text-color);
	word-break: break-all;
}

.token-meta {
	font-size: 0.85rem;
	color: #888;
	margin-top: 4px;
}

.token-actions {
	display: flex;
	gap: 8px;
	margin-left: 16px;
}

.btn-icon {
	width: 32px;
	height: 32px;
	border-radius: 6px;
	background-color: var(--light-bg);
	border: 1px solid var(--border-color);
	display: flex;
	align-items: center;
	justify-content: center;
	cursor: pointer;
	transition: var(--transition);
}

.btn-icon:hover {
	background-color: var(--hover-bg);
}

.delete-btn:hover {
	background-color: var(--accent-color);
}

@media (max-width: 1023px) {
	.section-header {
		flex-direction: column;
		align-items: flex-start;
		gap: 12px;
	}

	.token-item {
		flex-direction: column;
		align-items: flex-start;
		gap: 10px;
	}

	.token-actions {
		align-self: flex-end;
	}
}
</style>