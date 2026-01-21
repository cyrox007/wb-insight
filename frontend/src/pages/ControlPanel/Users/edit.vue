<script setup>
import CP_Users from '@/API/ControlPanel/CP_Users';
import { ref, onMounted } from 'vue';
import { useRoute } from 'vue-router';

const route = useRoute();
const targetUser = ref(null);
const isLoading = ref(false);
const showEditModal = ref(false);

onMounted(async () => {
	await loadUser();
});

const loadUser = async () => {
	isLoading.value = true;
	try {
		const { data } = await CP_Users.getUserByUuid(route.params.id);
		if (data?.status === 'success') {
			targetUser.value = data.data.target_user;
		}
	} catch (error) {
		console.error('Ошибка загрузки пользователя:', error);
	} finally {
		isLoading.value = false;
	}
};
</script>
<template>
	<div class="user-detail-container">
		<div v-if="isLoading" class="loading-state">
			Загрузка данных пользователя...
		</div>

		<div v-else-if="!targetUser" class="empty-state">
			Пользователь не найден
		</div>

		<div v-else class="user-card">
			<div class="user-header">
				<div>
					<h1 class="user-name">{{ targetUser.full_name }}</h1>
					<p class="user-email">{{ targetUser.email }}</p>
					<p v-if="targetUser.phone" class="user-phone">{{ targetUser.phone }}</p>
				</div>
				<div class="user-status-badge" :class="{ 'active': targetUser.is_active }">
					{{ targetUser.is_active ? 'Активен' : 'Неактивен' }}
				</div>
			</div>

			<div class="user-info-grid">
				<div class="info-item">
					<span class="info-label">ID</span>
					<code class="info-value">{{ targetUser.id }}</code>
				</div>
				<div class="info-item">
					<span class="info-label">Тип юр. лица</span>
					<span class="info-value">
						{{ targetUser.entity_type === 'individual' ? 'Физическое лицо' : 'Юридическое лицо' }}
					</span>
				</div>
				<div class="info-item">
					<span class="info-label">Создан</span>
					<span class="info-value">{{ new Date(targetUser.created_at).toLocaleDateString('ru-RU', {
						year: 'numeric',
						month: 'long',
						day: 'numeric',
						hour: '2-digit',
						minute: '2-digit'
					}) }}</span>
				</div>

				<div class="info-item">
					<span class="info-label">Часовой пояс</span>
					<span class="info-value">{{ targetUser.timezone }}</span>
				</div>

				<div v-if="targetUser.inn" class="info-item">
					<span class="info-label">ИНН</span>
					<span class="info-value">{{ targetUser.inn }}</span>
				</div>
				<div v-if="targetUser.kpp" class="info-item">
					<span class="info-label">КПП</span>
					<span class="info-value">{{ targetUser.kpp }}</span>
				</div>
				<div v-if="targetUser.legal_address" class="info-item">
					<span class="info-label">Юр. адрес</span>
					<span class="info-value">{{ targetUser.legal_address }}</span>
				</div>
				<div v-if="targetUser.department" class="info-item">
					<span class="info-label">Отдел</span>
					<span class="info-value">{{ targetUser.department }}</span>
				</div>
				<div v-if="targetUser.position" class="info-item">
					<span class="info-label">Должность</span>
					<span class="info-value">{{ targetUser.position }}</span>
				</div>
				<div class="info-item">
					<span class="info-label">Персонал</span>
					<span class="info-value">{{ targetUser.is_staff ? 'Да' : 'Нет' }}</span>
				</div>
			</div>
			<div class="user-actions">
				<button @click="openEditModal" class="btn btn-secondary">
					Редактировать профиль
				</button>
			</div>
		</div>
		<EditUserModal v-if="showEditModal" :is-open="true" :current-user="targetUser" @close="showEditModal = false"
			@updated="loadUser" />
	</div>
</template>
<style scoped>
.user-detail-container {
	padding: 24px;
	max-width: 1000px;
	margin: 0 auto;
}

.loading-state,
.empty-state {
	text-align: center;
	padding: 60px 20px;
	color: #aaa;
	font-style: italic;
}

.user-card {
	background-color: var(--card-bg);
	border: 1px solid var(--border-color);
	border-radius: 12px;
	padding: 28px;
	box-shadow: var(--shadow);
}

.user-header {
	display: flex;
	justify-content: space-between;
	align-items: flex-start;
	margin-bottom: 24px;
	flex-wrap: wrap;
	gap: 16px;
}

.user-name {
	font-size: 1.75rem;
	font-weight: 700;
	color: var(--text-color);
	margin: 0;
}

.user-email,
.user-phone {
	color: #ccc;
	margin: 4px 0 0 0;
}

.user-status-badge {
	padding: 6px 16px;
	border-radius: 20px;
	font-size: 0.9rem;
	font-weight: 600;
	background-color: rgba(231, 76, 60, 0.2);
	color: var(--accent-color);
}

.user-status-badge.active {
	background-color: rgba(46, 204, 113, 0.2);
	color: var(--success-color);
}

.user-info-grid {
	display: grid;
	grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
	gap: 20px;
	margin-bottom: 24px;
}

.info-item {
	display: flex;
	flex-direction: column;
}

.info-label {
	font-size: 0.85rem;
	color: #888;
	margin-bottom: 6px;
}

.info-value {
	font-size: 1rem;
	font-weight: 500;
	color: var(--text-color);
}

.info-value code {
	background: var(--medium-bg);
	padding: 2px 6px;
	border-radius: 4px;
	font-family: monospace;
	color: var(--secondary-color);
}

.user-actions {
	display: flex;
	justify-content: flex-end;
}
</style>