<script setup>
import { onMounted, ref } from 'vue'
import CP_Users from '@/API/ControlPanel/CP_Users'
import DateTransform from '@/utils/date_transform.js'
import BaseButton from '@/components/UI/Buttons/BaseButton.vue'

const isLoading = ref(false)
const loadError = ref('')
const users = ref([])

const ENTITY_LABELS = {
	individual: 'Физ. лицо',
	self_employed: 'Самозанятый',
	legal_entity: 'Юр. лицо'
}

const ROLE_LABELS = {
	super_admin: 'Суперадмин',
	admin: 'Админ',
	manager: 'Менеджер',
	support: 'Поддержка',
	analyst: 'Аналитик',
	user: 'Пользователь'
}

const getEntityLabel = (type) => ENTITY_LABELS[type] || type || '—'
const getRoleLabel = (role) => ROLE_LABELS[role?.role] || role?.role || '—'

const getEntityVariant = (type) => {
	if (type === 'individual') return 'cp-chip--info'
	if (type === 'self_employed') return 'cp-chip--warning'
	if (type === 'legal_entity') return 'cp-chip--accent'
	return ''
}

async function loadUsers() {
	isLoading.value = true
	loadError.value = ''
	try {
		const response = await CP_Users.getUserList()
		if (response.data?.status !== 'success' || !Array.isArray(response.data?.user_list)) {
			throw new Error('Некорректный ответ API пользователей')
		}
		users.value = response.data.user_list
	} catch (error) {
		console.error('Error fetching users:', error)
		users.value = []
		loadError.value = 'Не удалось загрузить список пользователей. Проверьте API панели управления.'
	} finally {
		isLoading.value = false
	}
}

onMounted(loadUsers)
</script>

<template>
	<section class="cp-page">
		<header class="cp-page-header">
			<div>
				<p class="cp-eyebrow">Аккаунты</p>
				<h2 class="cp-detail-title">Пользователи</h2>
				<p class="cp-subtitle">Просмотр зарегистрированных аккаунтов, ролей и текущего статуса.</p>
			</div>
		</header>

		<div v-if="isLoading" class="cp-state" role="status">
			Загружаем пользователей…
		</div>

		<div v-else-if="loadError" class="cp-state cp-state--error" role="alert">
			<div class="cp-state__stack">
				<strong>{{ loadError }}</strong>
				<BaseButton variant="outline" size="small" text="Повторить" @click="loadUsers" />
			</div>
		</div>

		<div v-else-if="users.length === 0" class="cp-state">
			Пользователей пока нет.
		</div>

		<div v-else class="cp-table-wrap">
			<div class="cp-table__toolbar">
				<strong>Все пользователи</strong>
				<span class="cp-table__count">{{ users.length }} записей</span>
			</div>
			<div class="cp-table-scroll">
				<table class="cp-table">
					<thead>
						<tr>
							<th>Пользователь</th>
							<th>Email</th>
							<th>Телефон</th>
							<th>Тип</th>
							<th>Роли</th>
							<th>Статус</th>
							<th>Регистрация</th>
							<th>Действия</th>
						</tr>
					</thead>
					<tbody>
						<tr v-for="user in users" :key="user.id">
							<td>
								<div class="cp-person">
									<div class="cp-avatar">{{ user.full_name?.charAt(0).toUpperCase() || 'U' }}</div>
									<div>
										<div class="cp-person__name">{{ user.full_name || 'Не указано' }}</div>
										<code class="cp-code" :title="user.id">{{ user.id.substring(0, 8) }}…</code>
									</div>
								</div>
							</td>
							<td>{{ user.email }}</td>
							<td>{{ user.phone || '—' }}</td>
							<td>
								<span class="cp-chip" :class="getEntityVariant(user.entity_type)">
									{{ getEntityLabel(user.entity_type) }}
								</span>
							</td>
							<td>
								<div class="cp-chip-row">
									<span v-for="role in user.roles" :key="role.role" class="cp-chip cp-chip--accent">
										{{ getRoleLabel(role) }}
									</span>
									<span v-if="!user.roles?.length" class="cp-muted">—</span>
								</div>
							</td>
							<td>
								<span class="cp-chip" :class="user.is_active ? 'cp-chip--active' : 'cp-chip--inactive'">
									{{ user.is_active ? 'Активен' : 'Неактивен' }}
								</span>
							</td>
							<td>{{ DateTransform.formatDate(user.created_at) }}</td>
							<td>
								<button
									class="cp-icon-button"
									@click="$router.push({ name: 'control-panel.edit-user', params: { id: user.id } })"
									title="Редактировать"
									aria-label="Редактировать пользователя"
								>
									<svg width="16" height="16" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
										<path d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z" />
									</svg>
								</button>
							</td>
						</tr>
					</tbody>
				</table>
			</div>
		</div>
	</section>
</template>
