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

			<FormRow>
				<SelectInput v-model="tokenType" label="Тип токена" :options="[
					{ value: 'personal', label: 'Персональный' },
					{ value: 'service', label: 'Сервисный' }
				]" :disabled="loading" />

				<TextInput v-model="marketplace" label="Магазин" disabled />
			</FormRow>

			<TextareaInput v-model="token" type="textarea" label="WB API токен" placeholder="Вставьте токен продавца..."
				:error="errorMessage" :disabled="loading" :rows="5" />

			<div class="hint">
				<strong>Требования к токену и типы токенов:</strong>
				<ul>
					<li><b>Персональный токен</b> — выдается в личном кабинете продавца. Wildberries не рекомендует
						использовать его в сервисах (только для личного ПО), но формально работает. Мы шифруем его своим
						алгоритмом для безопасности и не передаем третьим лицам.</li>
					<li><b>Сервисный токен</b> — новый тип токена, создается через раздел "Сервисные токены" в кабинете.
						Обычно связан с конкретным сервисом. Мы работаем над возможностью выбора нашего ПО при создании
						сервисного токена.</li>
					<li><b>Базовый токен</b> — имеет жесткие ограничения API, которые не совпадают с лимитами подписки.
						Данные могут быть устаревшими. Не рекомендуется к использованию.</li>
					<li><b>Тестовый токен</b> — только для тестирования. Не рекомендуется вводить в систему.</li>
				</ul>
				<p><b>Важно:</b> Для работы требуется токен с доступом к категории
					"Финансы", "Аналитика", "Контент" или "Продвижение" и "Статистика". Срок действия токена — 180 дней.
				</p>
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
import FormRow from '@/components/UI/FormCustum/FormRow.vue'
import SelectInput from '@/components/UI/SelectInput.vue'

// API
import ProfileServices from '@/API/Dashboard/ProfileServices'

const props = defineProps({
	isOpen: Boolean
})

const emit = defineEmits(['close', 'success'])

const token = ref('')
const label = ref('')
const tokenType = ref('personal')
const marketplace = ref('WB')
const loading = ref(false)
const errorMessage = ref(null)

// --- close ---
const close = () => {
	if (loading.value) return
	errorMessage.value = null
	token.value = ''
	label.value = ''
	tokenType.value = 'personal'
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
			token: token.value.trim(),
			label: label.value.trim(),
			token_type: tokenType.value,
			marketplace: marketplace.value
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

.form-row {
	display: flex;
	gap: 15px;
	margin-bottom: 15px;
}

.form-group {
	flex: 1;
	display: flex;
	flex-direction: column;
}

.form-group label {
	font-size: 13px;
	color: #555;
	margin-bottom: 5px;
	font-weight: 500;
}

.token-type-select {
	padding: 8px 12px;
	border: 1px solid #ddd;
	border-radius: 6px;
	font-size: 14px;
	background-color: #fff;
	cursor: pointer;
}

.token-type-select:disabled {
	background-color: #f5f5f5;
	cursor: not-allowed;
}

.marketplace-input {
	padding: 8px 12px;
	border: 1px solid #ddd;
	border-radius: 6px;
	font-size: 14px;
	background-color: #f5f5f5;
	color: #666;
	cursor: not-allowed;
}

.hint ul {
	margin: 8px 0 0 20px;
	padding: 0;
}

.hint li {
	margin-bottom: 4px;
	line-height: 1.4;
}
</style>