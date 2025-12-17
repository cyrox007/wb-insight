<template>
	<div v-if="isLoading">Загрузка...</div>
	<div v-else class="table-container">
		<table class="users-table">
			<thead>
				<tr>
					<th>ID</th>
					<th>Имя</th>
					<th>Email</th>
					<th>Телефон</th>
					<th>Тип</th>
					<th>Статус</th>
					<th>Дата регистрации</th>
					<th>Действия</th>
				</tr>
			</thead>
			<tbody>
				<tr v-for="user in users">
					<td class="user-id">{{ user.id.substring(0, 8) }}...</td>
					<td>
						<div class="user-info">
							<div class="user-avatar-small">{{ user.full_name?.charAt(0) || 'U' }}</div>
							<span class="user-name">{{ user.full_name || 'Не указано' }}</span>
						</div>
					</td>
					<td>{{ user.email }}</td>
					<td>{{ user.phone || 'Не указан' }}</td>
					<td>
						<span :class="['badge', user.entity_type === 'individual' ? 'badge-info' : 'badge-warning']">
							{{ user.entity_type === 'individual' ? 'Физ. лицо' : 'Юр. лицо' }}
						</span>
					</td>
					<td>
						<span :class="['status-badge', user.is_active ? 'active' : 'inactive']">
							{{ user.is_active ? 'Активен' : 'Неактивен' }}
						</span>
					</td>
					<td>{{ formatDate(user.created_at) }}</td>
					<td>
						<div class="action-buttons">
							<button class="btn-icon" @click="editUser(user)" title="Редактировать">
								<svg class="icon-sm" fill="currentColor" viewBox="0 0 20 20">
									<path
										d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z" />
								</svg>
							</button>
							<button :class="['btn-icon', user.is_active ? 'danger' : 'success']"
								@click="toggleUserStatus(user)"
								:title="user.is_active ? 'Деактивировать' : 'Активировать'">
								<svg class="icon-sm" fill="currentColor" viewBox="0 0 20 20">
									<path v-if="user.is_active"
										d="M13.477 14.89A6 6 0 015.11 6.524l8.367 8.368zm1.414-1.414L6.524 5.11a6 6 0 018.367 8.367zM18 10a8 8 0 11-16 0 8 8 0 0116 0z" />
									<path v-else d="M10 12a2 2 0 100-4 2 2 0 000 4z" />
								</svg>
							</button>
							<button class="btn-icon" @click="viewDetails(user)" title="Подробнее">
								<svg class="icon-sm" fill="currentColor" viewBox="0 0 20 20">
									<path d="M10 12a2 2 0 100-4 2 2 0 000 4z" />
									<path fill-rule="evenodd"
										d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z"
										clip-rule="evenodd" />
								</svg>
							</button>
						</div>
					</td>
				</tr>
			</tbody>
		</table>
	</div>
</template>

<script setup>
import { onMounted, ref } from 'vue';
import ControlPanelService from '@/API/ControlPanelService';

const isLoading = ref(false);
const users = ref([]);

const formatDate = (dateString) => {
	const date = new Date(dateString);
	return date.toLocaleDateString('ru-RU', {
		day: '2-digit',
		month: '2-digit',
		year: 'numeric'
	});
};


onMounted(async () => {
	isLoading.value = true;
	try {
		const response = await ControlPanelService.getUserList();
		users.value = response.data.data.user_list;
	} catch (error) {
		console.error('Error fetching users:', error);
	}
	isLoading.value = false;
});
</script>

<style scoped>
.table-container {
	overflow-x: auto;
	background-color: var(--card-bg);
	border-radius: 8px;
	box-shadow: var(--shadow);
}

.users-table {
	width: 100%;
	border-collapse: collapse;
}

.users-table th {
	padding: 1rem;
	text-align: left;
	background-color: var(--medium-bg);
	color: var(--text-color);
	font-weight: 600;
	border-bottom: 1px solid var(--border-color);
}

.users-table td {
	padding: 1rem;
	border-bottom: 1px solid var(--border-color);
}

.users-table tbody tr {
	transition: var(--transition);
}

.users-table tbody tr:hover {
	background-color: var(--hover-bg);
}

.action-buttons {
	display: flex;
	gap: 0.5rem;
}

.btn-icon {
	width: 32px;
	height: 32px;
	display: flex;
	align-items: center;
	justify-content: center;
	background: none;
	border: 1px solid var(--border-color);
	border-radius: 4px;
	color: var(--text-color);
	cursor: pointer;
	transition: var(--transition);
}

.btn-icon:hover {
	background-color: var(--hover-bg);
}

.btn-icon.danger:hover {
	background-color: rgba(231, 76, 60, 0.1);
	color: #e74c3c;
	border-color: #e74c3c;
}

.btn-icon.success:hover {
	background-color: rgba(46, 204, 113, 0.1);
	color: #2ecc71;
	border-color: #2ecc71;
}
</style>