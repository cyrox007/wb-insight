<script setup>
import { ref, watch } from 'vue'
import Modal from '@/components/UI/Modal.vue'
import TextInput from '@/components/UI/TextInput.vue'
import BaseButton from '@/components/UI/Buttons/BaseButton.vue'
import FormMessage from '@/components/UI/FormMessage.vue'
import CP_Users from '@/API/ControlPanel/CP_Users'

const props = defineProps({
	isOpen: Boolean,
	currentUser: Object
})

const emit = defineEmits(['close', 'updated'])

const userData = ref({
	full_name: '',
	email: '',
	phone: '',
	entity_type: 'individual',
	inn: '',
	kpp: '',
	legal_address: ''
})

watch(
	() => props.currentUser,
	(newUser) => {
		if (!newUser) return
		userData.value = {
			full_name: newUser.full_name || '',
			email: newUser.email || '',
			phone: newUser.phone || '',
			entity_type: newUser.entity_type || 'individual',
			inn: newUser.inn || '',
			kpp: newUser.kpp || '',
			legal_address: newUser.legal_address || ''
		}
	},
	{ immediate: true }
)

const isSaving = ref(false)
const formMessage = ref('')
const msgStatus = ref('')

async function saveUser() {
	isSaving.value = true
	formMessage.value = ''
	msgStatus.value = ''

	try {
		const payload = {
			full_name: userData.value.full_name.trim(),
			entity_type: userData.value.entity_type,
			inn: userData.value.inn.trim() || null,
			kpp: userData.value.kpp.trim() || null,
			legal_address: userData.value.legal_address.trim() || null
		}

		const response = await CP_Users.updateUser(props.currentUser.id, payload)
		if (response.data?.status === 'success') {
			emit('updated')
			emit('close')
			return
		}
		throw new Error(response.data?.message || 'Не удалось сохранить пользователя')
	} catch (error) {
		formMessage.value = error.response?.data?.error?.message || error.message || 'Ошибка при сохранении пользователя'
		msgStatus.value = 'error'
	} finally {
		isSaving.value = false
	}
}
</script>

<template>
	<Modal :is-open="isOpen" size="large" @close="$emit('close')">
		<template #header>
			<h3 class="cp-modal-title">Редактировать пользователя</h3>
		</template>
		<template #body>
			<div class="cp-form-grid">
				<TextInput label="ФИО / название" v-model="userData.full_name" placeholder="Введите имя или название" />
				<TextInput label="Email" v-model="userData.email" type="email" :disabled="true" />
				<TextInput label="Телефон" v-model="userData.phone" :disabled="true" />

				<div class="cp-form-row">
					<label class="cp-form-label">Тип аккаунта</label>
					<select v-model="userData.entity_type" class="cp-form-select">
						<option value="individual">Физическое лицо</option>
						<option value="self_employed">Самозанятый</option>
						<option value="legal_entity">Юридическое лицо</option>
					</select>
				</div>

				<template v-if="userData.entity_type === 'legal_entity'">
					<TextInput label="ИНН" v-model="userData.inn" placeholder="Введите ИНН" />
					<TextInput label="КПП" v-model="userData.kpp" placeholder="Введите КПП" />
					<TextInput label="Юридический адрес" v-model="userData.legal_address" placeholder="Введите юридический адрес" />
				</template>
			</div>

			<FormMessage v-if="formMessage" :message="formMessage" :message-type="msgStatus" />
		</template>
		<template #footer>
			<div class="cp-modal-footer">
				<BaseButton variant="outline" text="Отмена" @click="$emit('close')" />
				<BaseButton variant="primary" text="Сохранить" :loading="isSaving" @click="saveUser" />
			</div>
		</template>
	</Modal>
</template>
