<script setup>
import { ref, watch } from 'vue';
import Modal from '@/components/UI/Modal.vue';
import TextInput from '@/components/UI/TextInput.vue';
import ButtonCancel from '@/components/UI/Buttons/ButtonCancel.vue';
import ButtonPrimary from '@/components/UI/Buttons/ButtonPrimary.vue';
import FormMessage from '@/components/UI/FormMessage.vue';
import CP_Users from '@/API/ControlPanel/CP_Users';

const props = defineProps({
	isOpen: Boolean,
	currentUser: Object
});

const emit = defineEmits(['close', 'updated']);

const userData = ref({
	full_name: '',
	email: '',
	phone: '',
	entity_type: 'individual',
	inn: '',
	kpp: '',
	legal_address: '',
	is_active: false
});

// Инициализация данных
watch(
	() => props.currentUser,
	(newUser) => {
		if (newUser) {
			userData.value = {
				full_name: newUser.full_name || '',
				email: newUser.email || '',
				phone: newUser.phone || '',
				entity_type: newUser.entity_type || 'individual',
				inn: newUser.inn || '',
				kpp: newUser.kpp || '',
				legal_address: newUser.legal_address || '',
				is_active: Boolean(newUser.is_active)
			};
		}
	},
	{ immediate: true }
);

const modalLoadedBtn = ref(false);
const formMessage = ref('');
const msgStatus = ref('');

const saveUser = async () => {
	modalLoadedBtn.value = true;
	formMessage.value = '';
	msgStatus.value = '';

	try {
		// Подготавливаем данные
		const payload = {
			full_name: userData.value.full_name.trim(),
			email: userData.value.email.trim(),
			phone: userData.value.phone.trim() || null,
			entity_type: userData.value.entity_type,
			inn: userData.value.inn.trim() || null,
			kpp: userData.value.kpp.trim() || null,
			legal_address: userData.value.legal_address.trim() || null,
			is_active: userData.value.is_active
		};

		const response = await CP_Users.updateUser(props.currentUser.id, payload);

		if (response.data?.status === 'success') {
			emit('updated');
			emit('close');
		}
	} catch (error) {
		formMessage.value = error.response?.data?.message || 'Ошибка при сохранении пользователя';
		msgStatus.value = 'error';
	} finally {
		modalLoadedBtn.value = false;
	}
};
</script>

<template>
	<Modal :is-open="isOpen" @close="$emit('close')">
		<template #header>
			<h3>Редактировать пользователя</h3>
		</template>
		<template #body>
			<div class="form-grid">
				<TextInput label="ФИО" v-model="userData.full_name" placeholder="Введите полное имя" />
				<TextInput label="Email" v-model="userData.email" placeholder="Введите email" type="email"
					:disabled="true" />
				<TextInput label="Телефон" v-model="userData.phone" placeholder="Введите телефон" :disabled="true" />

				<div class="form-row">
					<label class="form-label">Тип юр. лица</label>
					<select v-model="userData.entity_type" class="form-select">
						<option value="individual">Физическое лицо</option>
						<option value="legal">Юридическое лицо</option>
					</select>
				</div>

				<TextInput v-if="userData.entity_type === 'legal'" label="ИНН" v-model="userData.inn"
					placeholder="Введите ИНН" />
				<TextInput v-if="userData.entity_type === 'legal'" label="КПП" v-model="userData.kpp"
					placeholder="Введите КПП" />
				<TextInput v-if="userData.entity_type === 'legal'" label="Юридический адрес"
					v-model="userData.legal_address" placeholder="Введите юридический адрес" />

				<div class="form-group">
					<label class="toggle-label">
						Активен
						<div class="toggle-switch" @click="userData.is_active = !userData.is_active">
							<div class="toggle-slider" :class="{ 'toggle-on': userData.is_active }"></div>
						</div>
					</label>
				</div>
			</div>

			<FormMessage v-if="formMessage" :message="formMessage" :message-type="msgStatus" />
		</template>
		<template #footer>
			<ButtonCancel @click="$emit('close')" text="Отмена" />
			<ButtonPrimary @click="saveUser" :loading="modalLoadedBtn" text="Сохранить" />
		</template>
	</Modal>
</template>

<style scoped>
.form-grid {
	display: grid;
	gap: 16px;
}

.form-row {
	display: flex;
	flex-direction: column;
}

.form-label {
	font-weight: 500;
	color: var(--text-color);
	margin-bottom: 6px;
	font-size: 0.95rem;
}

.form-select {
	padding: 10px 12px;
	border: 1px solid var(--border-color);
	border-radius: 6px;
	background-color: var(--card-bg);
	color: var(--text-color);
	font-size: 1rem;
}

.form-group {
	margin-top: 8px;
}

/* Toggle styles (reuse from tariff modal) */
.toggle-label {
	display: flex;
	justify-content: space-between;
	align-items: center;
	font-weight: 500;
	color: var(--text-color);
	cursor: pointer;
	user-select: none;
}

.toggle-switch {
	position: relative;
	width: 50px;
	height: 26px;
}

.toggle-slider {
	position: absolute;
	top: 0;
	left: 0;
	width: 100%;
	height: 100%;
	background-color: #555;
	border-radius: 13px;
	transition: var(--transition);
	cursor: pointer;
}

.toggle-slider::before {
	content: '';
	position: absolute;
	height: 22px;
	width: 22px;
	left: 2px;
	bottom: 2px;
	background-color: white;
	border-radius: 50%;
	transition: var(--transition);
}

.toggle-slider.toggle-on {
	background-color: var(--success-color);
}

.toggle-slider.toggle-on::before {
	transform: translateX(24px);
}
</style>