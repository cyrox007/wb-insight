<script setup>
import { onMounted, ref } from 'vue';
import CP_Users from '@/API/ControlPanel/CP_Users';
import DateTransform from '@/utils/date_transform.js';

const isLoading = ref(false);
const users = ref([]);

// Маппинги для лейблов
const ENTITY_LABELS = {
	individual: 'Физ. лицо',
	self_employed: 'Самозанятый',
	legal_entity: 'Юр. лицо'
};

const ROLE_LABELS = {
	super_admin: 'Суперадмин',
	admin: 'Админ',
	manager: 'Менеджер',
	support: 'Поддержка',
	analyst: 'Аналитик',
	user: 'Пользователь'
};

const getEntityLabel = (type) => ENTITY_LABELS[type] || type;
const getRoleLabel = (role) => ROLE_LABELS[role] || role;

const getEntityClass = (type) => {
	switch (type) {
		case 'individual': return 'individual';
		case 'self_employed': return 'self-employed';
		case 'legal_entity': return 'legal';
		default: return 'unknown';
	}
};

onMounted(async () => {
	isLoading.value = true;
	try {
		const response = await CP_Users.getUserList();
		users.value = response.data.user_list || [];
	} catch (error) {
		console.error('Error fetching users:', error);
	} finally {
		isLoading.value = false;
	}
});
</script>

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
					<th>Роли</th>
					<th>Статус</th>
					<th>Дата регистрации</th>
					<th>Действия</th>
				</tr>
			</thead>
			<tbody>
				<tr v-for="user in users" :key="user.id">
					<td class="user-id" :title="user.id">{{ user.id.substring(0, 8) }}…</td>
					<td>
						<div class="user-info">
							<div class="user-avatar-small">{{ user.full_name?.charAt(0).toUpperCase() || 'U' }}</div>
							<span class="user-name">{{ user.full_name || 'Не указано' }}</span>
						</div>
					</td>
					<td>{{ user.email }}</td>
					<td>{{ user.phone || '—' }}</td>
					<td>
						<span :class="['entity-badge', getEntityClass(user.entity_type)]">
							{{ getEntityLabel(user.entity_type) }}
						</span>
					</td>
					<td>
						<span v-for="role in user.roles" :key="role" class="role-badge">
							{{ getRoleLabel(role) }}
						</span>
					</td>
					<td>
						<span :class="['status-badge', user.is_active ? 'active' : 'inactive']">
							{{ user.is_active ? 'Активен' : 'Неактивен' }}
						</span>
					</td>
					<td>{{ DateTransform.formatDate(user.created_at) }}</td>
					<td>
						<div class="action-buttons">
							<button class="btn-icon"
								@click="$router.push({ name: 'control-panel.edit-user', params: { id: user.id } })"
								title="Редактировать">
								<svg class="icon-sm" fill="currentColor" viewBox="0 0 20 20">
									<path
										d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z" />
								</svg>
							</button>
						</div>
					</td>
				</tr>
			</tbody>
		</table>
	</div>
</template>

<style scoped>
.table-container {
	overflow-x: auto;
	background-color: var(--card-bg);
	border-radius: 12px;
	box-shadow: var(--shadow);
	padding: 1rem;
}

.users-table {
	width: 100%;
	border-collapse: collapse;
	font-size: 0.95rem;
}

.users-table th {
	padding: 1rem 0.75rem;
	text-align: left;
	background-color: var(--medium-bg);
	color: var(--text-color-secondary);
	font-weight: 600;
	font-size: 0.85rem;
	text-transform: uppercase;
	letter-spacing: 0.5px;
	border-bottom: 2px solid var(--border-color);
}

.users-table td {
	padding: 1rem 0.75rem;
	border-bottom: 1px solid var(--border-color-light);
	vertical-align: middle;
}

.users-table tbody tr {
	transition: background-color 0.2s ease;
}

.users-table tbody tr:hover {
	background-color: var(--hover-bg);
}

/* User Info */
.user-info {
	display: flex;
	align-items: center;
	gap: 0.75rem;
}

.user-avatar-small {
	width: 32px;
	height: 32px;
	border-radius: 50%;
	background-color: var(--primary-light);
	color: var(--primary);
	font-weight: 600;
	display: flex;
	align-items: center;
	justify-content: center;
	flex-shrink: 0;
}

.user-name {
	font-weight: 500;
	color: var(--text-color);
}

/* Badges */
.entity-badge,
.role-badge,
.status-badge {
	display: inline-block;
	padding: 0.25rem 0.5rem;
	border-radius: 12px;
	font-size: 0.8rem;
	font-weight: 500;
}

.entity-badge.individual {
	background-color: #e3f2fd;
	color: #1976d2;
}

.entity-badge.self-employed {
	background-color: #fff8e1;
	color: #ff8f00;
}

.entity-badge.legal {
	background-color: #f1f8e9;
	color: #388e3c;
}

.role-badge {
	background-color: #f5f5f5;
	color: #000;
	margin-right: 0.25rem;
	margin-bottom: 0.25rem;
}

.status-badge.active {
	background-color: #e8f5e9;
	color: #2e7d32;
}

.status-badge.inactive {
	background-color: #ffebee;
	color: #c62828;
}

/* Actions */
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
	border-radius: 6px;
	color: var(--text-color);
	cursor: pointer;
	transition: all 0.2s ease;
}

.btn-icon:hover {
	background-color: var(--primary-lighter);
	border-color: var(--primary);
	color: var(--primary);
}

/* Responsive */
@media (max-width: 768px) {
	.users-table {
		font-size: 0.85rem;
	}

	.users-table th,
	.users-table td {
		padding: 0.75rem 0.5rem;
	}

	.user-avatar-small {
		width: 28px;
		height: 28px;
		font-size: 0.85rem;
	}
}
</style>