<template>
	<Modal :is-open="isOpen" @close="close">
		<!-- HEADER -->
		<template #header>
			<div class="modal-header">
				<h3>Добавить токен Wildberries</h3>
				<!-- <button class="close-btn" @click="close">✕</button> -->
			</div>
		</template>

		<!-- BODY -->
		<template #body>
			<TextInput v-model="label" placeholder="Название токена..." />
			<TextareaInput v-model="token" type="textarea" label="WB API токен" placeholder="Вставьте токен продавца..."
				:error="errorMessage" :disabled="loading" :rows="5" />

			<div class="hint">
				Токен используется только для чтения данных (Analytics, Statistics, Promotion)
			</div>
		</template>

		<!-- FOOTER -->
		<template #footer>
			<ButtonCancel @click="close" :disabled="loading" />

			<ButtonSuccess text="Добавить токен" :loading="loading" @click="submit" />
		</template>
	</Modal>
</template>

<script setup>
import { ref } from 'vue'
import { notify } from '@/composables/notification'

// UI
import Modal from '@/components/UI/Modal.vue'
import TextInput from '@/components/UI/TextInput.vue'
import TextareaInput from '@/components/UI/TextareaInput.vue'
import ButtonSuccess from '@/components/UI/Buttons/ButtonSuccess.vue'
import ButtonCancel from '@/components/UI/Buttons/ButtonCancel.vue'

// API
import ProfileServices from '@/API/Dashboard/ProfileServices'

const props = defineProps({
	isOpen: Boolean
})

const emit = defineEmits(['close', 'success'])

const token = ref('')
const loading = ref(false)
const errorMessage = ref(null)

// --- close ---
const close = () => {
	if (loading.value) return
	errorMessage.value = null
	token.value = ''
	emit('close')
}

// --- validation ---
const validate = () => {
	if (!token.value || token.value.trim().length === 0) {
		return 'Введите токен'
	}

	if (token.value.length < 20) {
		return 'Токен слишком короткий'
	}

	return null
}

// --- submit ---
const submit = async () => {
	errorMessage.value = null

	const error = validate()
	if (error) {
		errorMessage.value = error
		return
	}

	try {
		loading.value = true

		const response = await ProfileServices.add_user_token({
			token: token.value.trim()
		})

		const result = response.data

		if (result.status === 'error') {
			errorMessage.value = result.error.message
			notify.error(result.error.message)
			return
		}

		notify.success('Токен успешно добавлен')
		emit('success')

	} catch (e) {
		console.error(e)
		errorMessage.value = 'Ошибка соединения с сервером'
		notify.error(errorMessage.value)
	} finally {
		loading.value = false
	}
}
</script>

<style scoped>
.close-btn {
	background: none;
	border: none;
	font-size: 18px;
	cursor: pointer;
}

.hint {
	margin-top: 10px;
	font-size: 12px;
	color: #888;
}
</style>