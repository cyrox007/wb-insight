<script setup>
import { ref, onMounted, watch } from 'vue';
import Modal from '@/components/UI/Modal.vue';
import ButtonCancel from '@/components/UI/Buttons/ButtonCancel.vue';
import ButtonPrimary from '@/components/UI/Buttons/ButtonPrimary.vue';
import TextInput from '@/components/UI/TextInput.vue';
import FormMessage from '@/components/UI/FormMessage.vue';
import CP_Roles from '@/API/ControlPanel/CP_Roles'; // ← ваш API для ролей

const props = defineProps({
	isOpen: Boolean,
	userId: String // ID пользователя, которому назначаем роль
});

const emit = defineEmits(['close', 'assigned']);

const modalLoadedBtn = ref(false);
const msg = ref('');
const msgType = ref('');
const selectedRole = ref('');
const rolesList = ref([]);
const isLoadingRoles = ref(false);

// Загружаем список ролей при открытии модалки
onMounted(async () => {
	if (props.isOpen) {
		await loadRoles();
	}
});

// Следим за изменением isOpen (на случай повторного открытия)
watch(() => props.isOpen, async (newVal) => {
	if (newVal) {
		await loadRoles();
	}
});
const ROLE_LABELS = {
	super_admin: 'Суперадмин',
	admin: 'Администратор',
	manager: 'Менеджер',
	support: 'Поддержка',
	analyst: 'Аналитик',
	user: 'Пользователь'
};

const loadRoles = async () => {
	isLoadingRoles.value = true;
	try {
		const response = await CP_Roles.getRolesList();
		if (response.data?.status === 'success') {
			rolesList.value = (response.data.data.roles || []).map(role => ({
				value: role,
				label: ROLE_LABELS[role] || role // fallback на случай новых ролей
			}));
		}
	} catch (error) {
		msg.value = 'Ошибка загрузки списка ролей';
		msgType.value = 'error';
	} finally {
		isLoadingRoles.value = false;
	}
};

const assignRole = async () => {
	if (!selectedRole.value) {
		msg.value = 'Выберите роль из списка';
		msgType.value = 'error';
		return;
	}

	modalLoadedBtn.value = true;
	msg.value = '';
	msgType.value = '';

	try {
		const response = await CP_Roles.assignRoleToUser(props.userId, selectedRole.value);

		if (response.data?.status === 'success') {
			msg.value = 'Роль успешно назначена';
			msgType.value = 'success';

			setTimeout(() => {
				emit('assigned'); // уведомляем родителя
				emit('close');
			}, 1000);
		} else {
			throw new Error(response.data?.message || 'Неизвестная ошибка');
		}
	} catch (error) {
		msg.value = error.message || 'Ошибка при назначении роли';
		msgType.value = 'error';
	} finally {
		modalLoadedBtn.value = false;
	}
};
</script>

<template>
	<Modal :is-open="isOpen" @close="$emit('close')">
		<template #header>
			<h3>Назначить роль</h3>
		</template>
		<template #body>
			<div class="form-group">
				<label class="form-label">Выберите роль</label>
				<select v-model="selectedRole" class="form-select" :disabled="isLoadingRoles">
					<option value="">-- Выберите роль --</option>
					<option v-for="role in rolesList" :key="role.value" :value="role.value">
						{{ role.label }}
					</option>
				</select>
			</div>

			<div v-if="isLoadingRoles" class="loading-text">
				Загрузка ролей...
			</div>
		</template>
		<template #footer>
			<FormMessage v-if="msg" :message-type="msgType" :message="msg" />
			<ButtonCancel @click="$emit('close')" text="Отмена" />
			<ButtonPrimary @click="assignRole" :loading="modalLoadedBtn" text="Назначить" />
		</template>
	</Modal>
</template>

<style scoped>
.form-group {
	margin-bottom: 16px;
}

.form-label {
	display: block;
	margin-bottom: 6px;
	font-size: 0.95rem;
	color: var(--text-color);
}

.form-select {
	width: 100%;
	padding: 10px 12px;
	border: 1px solid var(--border-color);
	border-radius: 6px;
	background-color: var(--medium-bg);
	color: var(--text-color);
	font-size: 1rem;
}

.loading-text {
	color: #888;
	font-style: italic;
	text-align: center;
	padding: 8px 0;
}
</style>