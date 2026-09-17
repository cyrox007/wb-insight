<script setup>
import CP_Users from '@/API/ControlPanel/CP_Users'
import CP_Roles from '@/API/ControlPanel/CP_Roles'
import DateTransform from '@/utils/date_transform'
import EditUserModal from '@/components/UserModals/edit_user.vue'
import AssignRoleModal from '@/components/UserModals/assign_role.vue'
import BaseButton from '@/components/UI/Buttons/BaseButton.vue'
import Modal from '@/components/UI/Modal.vue'
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const targetUser = ref(null)
const isLoading = ref(false)
const loadError = ref('')
const roleActionLoading = ref(false)
const showEditModal = ref(false)
const showAssignRoleModal = ref(false)
const roleConfirm = ref({ isOpen: false, role: '' })

const ENTITY_LABELS = {
	individual: 'Физическое лицо',
	self_employed: 'Самозанятый',
	legal_entity: 'Юридическое лицо'
}

onMounted(loadUser)

async function loadUser() {
	isLoading.value = true
	loadError.value = ''
	try {
		const { data } = await CP_Users.getUserByUuid(route.params.id)
		if (data?.status === 'success') {
			targetUser.value = data.target_user
		} else {
			targetUser.value = null
			loadError.value = 'Пользователь не найден.'
		}
	} catch (error) {
		console.error('Ошибка загрузки пользователя:', error)
		targetUser.value = null
		loadError.value = 'Не удалось загрузить данные пользователя.'
	} finally {
		isLoading.value = false
	}
}

function askRemoveRole(roleCode) {
	if (roleActionLoading.value) return
	roleConfirm.value = { isOpen: true, role: roleCode }
}

function closeRoleConfirm() {
	if (roleActionLoading.value) return
	roleConfirm.value = { isOpen: false, role: '' }
}

async function removeRoleConfirmed() {
	if (roleActionLoading.value || !targetUser.value || !roleConfirm.value.role) return
	roleActionLoading.value = true
	try {
		const response = await CP_Roles.deleteRoleFromUser(targetUser.value.id, roleConfirm.value.role)
		if (response.data?.status !== 'success') {
			throw new Error(response.data?.message || 'Не удалось удалить роль')
		}
		roleConfirm.value = { isOpen: false, role: '' }
		await loadUser()
	} catch (error) {
		console.error('Ошибка удаления роли:', error)
		loadError.value = error.response?.data?.error?.message || error.message || 'Не удалось удалить роль. Повторите действие.'
	} finally {
		roleActionLoading.value = false
	}
}
</script>

<template>
	<section class="cp-page">
		<header class="cp-page-header">
			<div>
				<p class="cp-eyebrow">Пользователи · профиль</p>
				<h2 class="cp-detail-title">Карточка пользователя</h2>
				<p class="cp-subtitle">Профиль, статус и роли пользователя.</p>
			</div>
			<BaseButton variant="outline" size="small" text="← К списку" @click="router.push({ name: 'control-panel.users' })" />
		</header>

		<div v-if="isLoading" class="cp-state" role="status">Загружаем данные пользователя…</div>

		<div v-else-if="loadError && !targetUser" class="cp-state cp-state--error" role="alert">
			<div class="cp-state__stack">
				<strong>{{ loadError }}</strong>
				<BaseButton variant="outline" size="small" text="Повторить" @click="loadUser" />
			</div>
		</div>

		<article v-else-if="targetUser" class="cp-card cp-detail-card">
			<div class="cp-detail-header">
				<div>
					<h3 class="cp-detail-title">{{ targetUser.full_name || 'Без имени' }}</h3>
					<p class="cp-detail-meta">{{ targetUser.email }}<span v-if="targetUser.phone"> · {{ targetUser.phone }}</span></p>
				</div>
				<span class="cp-chip" :class="targetUser.is_active ? 'cp-chip--active' : 'cp-chip--inactive'">
					{{ targetUser.is_active ? 'Активен' : 'Неактивен' }}
				</span>
			</div>

			<div v-if="loadError" class="cp-state cp-state--error" role="alert" style="min-height: auto; margin-bottom: 14px;">
				{{ loadError }}
			</div>

			<div class="cp-info-grid">
				<div class="cp-info-item"><span class="cp-info-label">ID</span><code class="cp-info-value cp-code">{{ targetUser.id }}</code></div>
				<div class="cp-info-item"><span class="cp-info-label">Тип аккаунта</span><span class="cp-info-value">{{ ENTITY_LABELS[targetUser.entity_type] || targetUser.entity_type || '—' }}</span></div>
				<div class="cp-info-item"><span class="cp-info-label">Создан</span><span class="cp-info-value">{{ DateTransform.formatDate(targetUser.created_at) }}</span></div>
				<div class="cp-info-item"><span class="cp-info-label">Часовой пояс</span><span class="cp-info-value">{{ targetUser.timezone || '—' }}</span></div>
				<div v-if="targetUser.inn" class="cp-info-item"><span class="cp-info-label">ИНН</span><span class="cp-info-value">{{ targetUser.inn }}</span></div>
				<div v-if="targetUser.kpp" class="cp-info-item"><span class="cp-info-label">КПП</span><span class="cp-info-value">{{ targetUser.kpp }}</span></div>
				<div v-if="targetUser.legal_address" class="cp-info-item"><span class="cp-info-label">Юр. адрес</span><span class="cp-info-value">{{ targetUser.legal_address }}</span></div>
				<div v-if="targetUser.department" class="cp-info-item"><span class="cp-info-label">Отдел</span><span class="cp-info-value">{{ targetUser.department }}</span></div>
				<div v-if="targetUser.position" class="cp-info-item"><span class="cp-info-label">Должность</span><span class="cp-info-value">{{ targetUser.position }}</span></div>
				<div class="cp-info-item"><span class="cp-info-label">Сотрудник</span><span class="cp-info-value">{{ targetUser.is_staff ? 'Да' : 'Нет' }}</span></div>
			</div>

			<section class="cp-section">
				<div class="cp-section-header">
					<div>
						<h3 class="cp-section-title">Роли и доступ</h3>
						<p class="cp-muted">Роль пользователя нельзя удалить; дополнительные роли можно отозвать.</p>
					</div>
					<BaseButton variant="success" size="small" text="Назначить роль" :disabled="roleActionLoading" @click="showAssignRoleModal = true" />
				</div>

				<div v-if="targetUser.roles?.length" class="cp-list">
					<div v-for="roleItem in targetUser.roles" :key="roleItem.role" class="cp-list-row">
						<div class="cp-list-row__main">
							<div class="cp-chip-row"><span class="cp-chip cp-chip--accent">{{ roleItem.role }}</span></div>
							<p class="cp-list-row__meta">
								Назначена: {{ DateTransform.formatDate(roleItem.assigned_at) }}
								<span v-if="roleItem.assigned_by"> · {{ roleItem.assigned_by }}</span>
							</p>
						</div>
						<button
							v-if="roleItem.role !== 'user'"
							class="cp-icon-button cp-icon-button--danger"
							title="Удалить роль"
							:aria-label="`Удалить роль ${roleItem.role}`"
							:disabled="roleActionLoading"
							@click="askRemoveRole(roleItem.role)"
						>×</button>
					</div>
				</div>
				<div v-else class="cp-state">Роли не назначены.</div>
			</section>

			<div class="cp-section cp-actions cp-actions--end">
				<BaseButton variant="primary" text="Редактировать профиль" :disabled="roleActionLoading" @click="showEditModal = true" />
			</div>
		</article>

		<EditUserModal v-if="showEditModal" :is-open="true" :current-user="targetUser" @close="showEditModal = false" @updated="loadUser" />
		<AssignRoleModal :is-open="showAssignRoleModal" :user-id="targetUser?.id" @close="showAssignRoleModal = false" @assigned="loadUser" />

		<Modal
			v-if="roleConfirm.isOpen"
			:is-open="true"
			aria-label="Подтверждение удаления роли"
			:close-on-overlay-click="!roleActionLoading"
			:close-on-escape="!roleActionLoading"
			@close="closeRoleConfirm"
		>
			<template #header><h3 class="cp-modal-title">Удалить роль</h3></template>
			<template #body><p class="cp-modal-copy">Удалить роль «{{ roleConfirm.role }}» у пользователя? Доступ изменится сразу после сохранения.</p></template>
			<template #footer>
				<div class="cp-modal-footer">
					<BaseButton variant="outline" text="Отмена" :disabled="roleActionLoading" @click="closeRoleConfirm" />
					<BaseButton variant="danger" text="Удалить роль" loading-text="Удаляем…" :loading="roleActionLoading" @click="removeRoleConfirmed" />
				</div>
			</template>
		</Modal>
	</section>
</template>
