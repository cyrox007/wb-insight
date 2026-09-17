<script setup>
import { onMounted, ref, watch } from 'vue'
import Modal from '@/components/UI/Modal.vue'
import BaseButton from '@/components/UI/Buttons/BaseButton.vue'
import FormMessage from '@/components/UI/FormMessage.vue'
import CP_Roles from '@/API/ControlPanel/CP_Roles'

const props = defineProps({
	isOpen: Boolean,
	userId: String
})

const emit = defineEmits(['close', 'assigned'])
const isSaving = ref(false)
const msg = ref('')
const msgType = ref('')
const selectedRole = ref('')
const rolesList = ref([])
const isLoadingRoles = ref(false)

const ROLE_LABELS = {
	super_admin: 'Суперадмин',
	admin: 'Администратор',
	manager: 'Менеджер',
	support: 'Поддержка',
	analyst: 'Аналитик',
	user: 'Пользователь'
}

async function loadRoles() {
	isLoadingRoles.value = true
	msg.value = ''
	msgType.value = ''
	selectedRole.value = ''
	try {
		const response = await CP_Roles.getRolesList()
		if (response.data?.status !== 'success' || !Array.isArray(response.data?.roles)) {
			throw new Error('Некорректный ответ API ролей')
		}
		rolesList.value = response.data.roles.map((role) => ({
			value: role,
			label: ROLE_LABELS[role] || role
		}))
	} catch (error) {
		console.error('Ошибка загрузки списка ролей:', error)
		rolesList.value = []
		msg.value = 'Не удалось загрузить список ролей.'
		msgType.value = 'error'
	} finally {
		isLoadingRoles.value = false
	}
}

async function assignRole() {
	if (isSaving.value || isLoadingRoles.value) return
	if (!selectedRole.value) {
		msg.value = 'Выберите роль из списка.'
		msgType.value = 'error'
		return
	}

	isSaving.value = true
	msg.value = ''
	msgType.value = ''
	try {
		const response = await CP_Roles.assignRoleToUser(props.userId, selectedRole.value)
		if (response.data?.status !== 'success') {
			throw new Error(response.data?.message || 'Не удалось назначить роль')
		}
		emit('assigned')
		emit('close')
	} catch (error) {
		msg.value = error.response?.data?.error?.message || error.message || 'Ошибка при назначении роли'
		msgType.value = 'error'
	} finally {
		isSaving.value = false
	}
}

onMounted(() => {
	if (props.isOpen) loadRoles()
})

watch(() => props.isOpen, (isOpen) => {
	if (isOpen) loadRoles()
})
</script>

<template>
	<Modal
		:is-open="isOpen"
		aria-label="Назначение роли пользователю"
		:close-on-overlay-click="!isSaving"
		:close-on-escape="!isSaving"
		@close="$emit('close')"
	>
		<template #header>
			<h3 class="cp-modal-title">Назначить роль</h3>
		</template>
		<template #body>
			<div class="cp-form-row" :aria-busy="isLoadingRoles || isSaving">
				<label class="cp-form-label">Роль</label>
				<select v-model="selectedRole" class="cp-form-select" :disabled="isLoadingRoles || isSaving">
					<option value="">{{ isLoadingRoles ? 'Загружаем роли…' : 'Выберите роль' }}</option>
					<option v-for="role in rolesList" :key="role.value" :value="role.value">
						{{ role.label }}
					</option>
				</select>
				<p class="cp-muted">Назначение роли изменит доступ пользователя к административным функциям.</p>
			</div>
			<FormMessage v-if="msg" :message-type="msgType" :message="msg" />
		</template>
		<template #footer>
			<div class="cp-modal-footer">
				<BaseButton variant="outline" text="Отмена" :disabled="isSaving" @click="$emit('close')" />
				<BaseButton
					variant="primary"
					text="Назначить"
					loading-text="Назначаем…"
					:loading="isSaving"
					:disabled="isLoadingRoles || !selectedRole"
					@click="assignRole"
				/>
			</div>
		</template>
	</Modal>
</template>
