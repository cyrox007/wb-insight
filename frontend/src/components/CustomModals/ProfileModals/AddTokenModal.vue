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
				<strong>Требования к токену WB Insight</strong>
				<ul>
					<li>
						До регистрации WB Insight в официальном Каталоге решений используйте
						<b>Базовый токен</b>. После регистрации будет использоваться
						<b>Сервисный токен</b>, выпущенный именно для WB Insight.
					</li>
					<li>
						Уровень доступа: <b>Только чтение</b>. Токены с правом изменения данных
						система не принимает.
					</li>
					<li>
						Обязательные категории: <b>Контент</b>, <b>Аналитика</b>,
						<b>Цены и скидки</b>, <b>Статистика</b>, <b>Продвижение</b> и <b>Финансы</b>.
					</li>
					<li>
						<b>Персональный токен</b> нельзя передавать облачному сервису;
						<b>Тестовый токен</b> работает только в sandbox. Оба типа будут отклонены.
					</li>
				</ul>
				<p>
					Тип, категории и срок действия определяются автоматически по JWT. Перед сохранением
					WB Insight дополнительно проверит токен через Wildberries, поэтому отозванный или
					неактивный токен подключить нельзя.
				</p>
			</div>

			<LegalConsentChecklist
				v-model="legalConsents"
				context="marketplace_credential"
				@valid="legalValid = $event"
			/>
		</template>

		<template #footer>
			<ButtonCancel @click="close" :disabled="loading" />
			<ButtonSuccess
				text="Добавить кабинет"
				:loading="loading"
				:disabled="!legalValid || loading"
				@click="submit"
			/>
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
import LegalConsentChecklist from '@/components/LegalConsentChecklist.vue'

import ProfileServices from '@/API/Dashboard/ProfileServices'

defineProps({
	isOpen: Boolean
})

const emit = defineEmits(['close', 'success'])

const token = ref('')
const label = ref('')
const loading = ref(false)
const errorMessage = ref(null)
const legalConsents = ref([])
const legalValid = ref(false)

const close = () => {
	if (loading.value) return
	errorMessage.value = null
	token.value = ''
	label.value = ''
	legalConsents.value = []
	legalValid.value = false
	emit('close')
}

const validate = () => {
	if (!token.value || token.value.trim().length === 0) {
		return 'Введите токен'
	}

	if (token.value.length < 20) {
		return 'Токен слишком короткий'
	}

	if (!legalValid.value) {
		return 'Примите актуальные условия подключения кабинета'
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
			label: label.value.trim(),
			legal_consents: legalConsents.value
		})

		const result = response.data

		if (result.status === 'error') {
			errorMessage.value = result.error.message
			notify.error(result.error.message)
			return
		}

		notify.success(
			result.message || 'Кабинет Wildberries подключён. Первичная синхронизация поставлена в очередь.'
		)
		emit('success', result.data)
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
</style>