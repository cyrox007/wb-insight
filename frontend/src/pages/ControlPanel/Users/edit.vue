<script setup>
import CP_Users from '@/API/ControlPanel/CP_Users';
import DateTransform from '@/utils/date_transform';
import EditUserModal from '@/components/UserModals/edit_user.vue';
import ChangePasswordModal from '@/components/UserModals/change_password.vue';
import AssignRoleModal from '@/components/UserModals/assign_role.vue';
import { ref, onMounted } from 'vue';
import { useRoute } from 'vue-router';
import ButtonPrimary from '@/components/UI/Buttons/ButtonPrimary.vue';
import ButtonOutline from '@/components/UI/Buttons/ButtonOutline.vue';
import ButtonSuccess from '@/components/UI/Buttons/ButtonSuccess.vue';
import CP_Roles from '@/API/ControlPanel/CP_Roles';

const route = useRoute();
const targetUser = ref(null);
const isLoading = ref(false);
const showEditModal = ref(false);
const showChangePasswordModal = ref(false);
const showAssignRoleModal = ref(false);

onMounted(async () => {
	await loadUser();
});

const loadUser = async () => {
	isLoading.value = true;
	try {
		const { data } = await CP_Users.getUserByUuid(route.params.id);
		if (data?.status === 'success') {
			targetUser.value = data.target_user;
		}
	} catch (error) {
		console.error('Ошибка загрузки пользователя:', error);
	} finally {
		isLoading.value = false;
	}
};

// Метод удаления роли
const removeRole = async (roleCode) => {
	if (!confirm(`Удалить роль "${roleCode}" у пользователя?`)) return;

	try {
		await CP_Roles.deleteRoleFromUser(targetUser.value.id, roleCode);
		// Обновляем данные пользователя
		await loadUser();
	} catch (error) {
		console.error('Ошибка удаления роли:', error);
		// Можно показать уведомление
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
			<!-- Блок ролей -->
			<div class="roles-section">
				<h3 class="section-title">Роли</h3>
				<div v-if="targetUser.roles && targetUser.roles.length > 0" class="roles-grid">
					<div v-for="(roleItem, index) in targetUser.roles" :key="`${roleItem.role}-${index}`"
						class="role-card">
						<div class="role-header">
							<div class="role-name">{{ roleItem.role }}</div>
							<!-- Кнопка удаления для всех ролей, кроме 'user' -->
							<button v-if="roleItem.role !== 'user'" @click="removeRole(roleItem.role)"
								class="role-remove-btn" title="Удалить роль">
								&times;
							</button>
						</div>
						<div class="role-meta">
							Назначена: {{ DateTransform.formatDate(roleItem.assigned_at) }}
							<span v-if="roleItem.assigned_by"> • {{ roleItem.assigned_by }}</span>
						</div>
					</div>
				</div>
				<p v-else class="no-roles">Роли не назначены</p>
			</div>
			<div class="user-actions">
				<ButtonPrimary @click="showEditModal = true" :text="'Редактировать профиль'" />
				<ButtonOutline @click="showChangePasswordModal = true" :text="'Сменить пароль'" />
				<ButtonSuccess @click="showAssignRoleModal = true" :text="'Назначить роль'" />
			</div>
		</div>
		<EditUserModal v-if="showEditModal" :is-open="true" :current-user="targetUser" @close="showEditModal = false"
			@updated="loadUser" />
		<ChangePasswordModal :is-open="showChangePasswordModal" :user-id="targetUser?.id"
			@close="showChangePasswordModal = false" />

		<AssignRoleModal :is-open="showAssignRoleModal" :user-id="targetUser?.id" @close="showAssignRoleModal = false"
			@assigned="loadUser" />
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
	gap: 8px;
	margin-top: 15px;
}

/* === Секция ролей === */
.roles-section {
	margin-top: 24px;
	padding-top: 24px;
	border-top: 1px solid var(--border-color);
}

.section-title {
	font-size: 1.1rem;
	color: var(--text-color);
	margin-bottom: 16px;
}

.roles-grid {
	display: grid;
	gap: 12px;
}

.role-card {
	background-color: var(--medium-bg);
	border-radius: 8px;
	padding: 12px 16px;
	border-left: 3px solid var(--secondary-color);
}

.role-name {
	font-weight: 600;
	color: var(--text-color);
	font-size: 1rem;
	margin-bottom: 4px;
}

.role-meta {
	font-size: 0.85rem;
	color: #aaa;
}

.no-roles {
	color: #888;
	font-style: italic;
	padding: 12px 0;
}

.role-header {
	display: flex;
	justify-content: space-between;
	align-items: center;
	margin-bottom: 4px;
}

.role-remove-btn {
	background: none;
	border: none;
	color: var(--accent-color);
	font-size: 1.4rem;
	width: 28px;
	height: 28px;
	display: flex;
	align-items: center;
	justify-content: center;
	border-radius: 50%;
	cursor: pointer;
	transition: var(--transition);
	opacity: 0.7;
}

.role-remove-btn:hover {
	background-color: rgba(231, 76, 60, 0.2);
	opacity: 1;
}
</style>