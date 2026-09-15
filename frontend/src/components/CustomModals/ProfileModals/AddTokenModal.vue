<template>
	<Modal :is-open="isOpen" @close="close">
		<template #header>
			<div class="modal-header">
				<h3>Добавить кабинет Wildberries</h3>
			</div>
		</template>

		<template #body>
			<TextInput v-model="label" placeholder="Название кабинета..." />

			<TextareaInput
				v-model="token"
				type="textarea"
				label="WB API токен"
				placeholder="Вставьте токен продавца..."
				:error="errorMessage"
				:disabled="loading"
				:rows="5"
			/>

			<div class="hint">
				<strong>Тип и срок действия определяются автоматически из токена.</strong>
				<ul>
					<li>
						<b>Базовый токен</b> — используйте для подключения облачного сервиса, пока WB Insight
						не зарегистрирован в каталоге сервисов Wildberries.
					</li>
					<li>
						<b>Сервисный токен</b> — будет принят после настройки идентификатора нашего сервиса
						в Wildberries; токен для другого сервиса будет отклонён.
					</li>
					<li>
						<b>Персональный токен</b> нельзя использовать в облачном сервисе и система его не сохранит.
					</li>
					<li>
						<b>Тестовый токен</b> предназначен для тестового контура WB и здесь не поддерживается.
					</li>
				</ul>
				<p>
					Для полной аналитики выдайте токену необходимые категории доступа к статистике,
					контенту, аналитике, финансам и продвижению. Фактическую дату окончания действия
					мы прочитаем из поля <code>exp</code> самого токена.
				</p>
			</div>
		</template>

		<template #footer>
			<ButtonCancel @click="close" :disabled="loading" />
			<ButtonSuccess text="Добавить кабинет" :loading="loading" @click="submit" />
		</template>
	</Modal>
</template>

<script setup>
import { ref } from 'vue'
import { notify } from '@/composables/notification'

import Modal from '@/components/UI/Modal.vue'
import TextInput from '@/components/UI/TextInput.vue'
import TextareaInput from '@/components/UI/TextareaInput.vue'
import ButtonSuccess from '@/components/UI/Buttons/ButtonSuccess.vue'
import ButtonCancel from '@/components/UI/Buttons/ButtonCancel.vue'

import ProfileServices from '@/API/Dashboard/ProfileServices'

defineProps({
	isOpen: Boolean
})

const emit = defineEmits(['close', 'success'])

const token = ref('')
const label = ref('')
const loading = ref(false)
const errorMessage = ref(null)

const close = () => {
	if (loading.value) return
	errorMessage.value = null
	token.value = ''
	label.value = ''
	emit('close')
}

const validate = () => {
	if (!token.value || token.value.trim().length === 0) {
		return 'Введите токен'
	}

	if (token.value.length < 20) {
		return 'Токен слишком короткий'
	}

	return null
}

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
			token: token.value.trim(),
			label: label.value.trim()
		})

		const result = response.data

		if (result.status === 'error') {
			errorMessage.value = result.error.message
			notify.error(result.error.message)
			return
		}

		notify.success('Кабинет Wildberries успешно добавлен')
		emit('success')
	} catch (e) {
		console.error(e)
		errorMessage.value =
			e?.response?.data?.error?.message || 'Ошибка соединения с сервером'
		notify.error(errorMessage.value)
	} finally {
		loading.value = false
	}
}
</script>

<style scoped>
.hint {
	margin-top: 10px;
	font-size: 12px;
	color: #707070;
}

.hint ul {
	margin: 8px 0 0 20px;
	padding: 0;
}

.hint li {
	margin-bottom: 6px;
	line-height: 1.45;
}

.hint p {
	margin: 10px 0 0;
	line-height: 1.45;
}

.hint code {
	font-size: inherit;
}
</style>
