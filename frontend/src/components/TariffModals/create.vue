<script setup>
import { ref, watch } from 'vue'
import Modal from '../UI/Modal.vue'
import TextInput from '../UI/TextInput.vue'
import TextareaInput from '../UI/TextareaInput.vue'
import BaseButton from '../UI/Buttons/BaseButton.vue'
import FormMessage from '../UI/FormMessage.vue'
import StringTransform from '@/utils/string_transform.js'
import CP_Tariffs from '@/API/ControlPanel/CP_Tariffs'

const props = defineProps({
	isOpen: Boolean
})

const emit = defineEmits(['close', 'created'])
const isSaving = ref(false)
const tariffCode = ref('')
const tariffName = ref('')
const tariffPrice = ref('')
const tariffDescription = ref('')
const isActive = ref(true)
const isPublic = ref(true)
const formMessage = ref('')
const messageType = ref('')

function resetForm() {
	tariffCode.value = ''
	tariffName.value = ''
	tariffPrice.value = ''
	tariffDescription.value = ''
	isActive.value = true
	isPublic.value = true
	formMessage.value = ''
	messageType.value = ''
}

watch(() => props.isOpen, (isOpen) => {
	if (isOpen) resetForm()
})

async function createTariff() {
	formMessage.value = ''
	messageType.value = ''

	if (!tariffCode.value.trim()) {
		formMessage.value = 'Укажите код тарифа.'
		messageType.value = 'error'
		return
	}
	if (!tariffName.value.trim()) {
		formMessage.value = 'Укажите название тарифа.'
		messageType.value = 'error'
		return
	}

	const priceStr = tariffPrice.value.trim()
	const priceNum = Number(priceStr.replace(',', '.'))
	if (!priceStr || !Number.isFinite(priceNum) || priceNum < 0) {
		formMessage.value = 'Цена должна быть неотрицательным числом.'
		messageType.value = 'error'
		return
	}

	isSaving.value = true
	try {
		const codeToSend = StringTransform.containsCyrillic(tariffCode.value)
			? StringTransform.transliterate(tariffCode.value)
			: tariffCode.value

		const response = await CP_Tariffs.createTariff({
			code: codeToSend.trim(),
			name: tariffName.value.trim(),
			price: Number(priceNum.toFixed(2)),
			description: tariffDescription.value.trim(),
			isActive: isActive.value,
			isPublic: isPublic.value
		})

		if (response.data?.status !== 'success') {
			throw new Error(response.data?.message || 'Не удалось создать тариф')
		}

		formMessage.value = 'Тариф создан.'
		messageType.value = 'success'
		emit('created')
		emit('close')
	} catch (error) {
		console.error('Ошибка создания тарифа:', error)
		formMessage.value = error.response?.data?.error?.message || error.message || 'Ошибка подключения к серверу'
		messageType.value = 'error'
	} finally {
		isSaving.value = false
	}
}
</script>

<template>
	<Modal :is-open="isOpen" size="large" @close="$emit('close')">
		<template #header>
			<h3 class="cp-modal-title">Создать тариф</h3>
		</template>

		<template #body>
			<div class="cp-form-grid">
				<TextInput v-model="tariffCode" label="Код тарифа" placeholder="Например: business" />
				<TextInput v-model="tariffName" label="Название" placeholder="Введите название тарифа" />
				<TextInput v-model="tariffPrice" label="Цена, ₽/мес" placeholder="0" type="number" />
				<TextareaInput v-model="tariffDescription" label="Описание" placeholder="Кратко опишите тариф" :rows="3" />

				<div class="cp-toggle-row">
					<div class="cp-toggle-row__copy">
						<div class="cp-toggle-row__label">Активный тариф</div>
						<div class="cp-toggle-row__hint">{{ isActive ? 'Доступен для подключения' : 'Отключён для подключения' }}</div>
					</div>
					<button type="button" class="cp-toggle" :class="{ 'cp-toggle--on': isActive }" :aria-pressed="isActive" @click="isActive = !isActive"></button>
				</div>

				<div class="cp-toggle-row">
					<div class="cp-toggle-row__copy">
						<div class="cp-toggle-row__label">Публичный тариф</div>
						<div class="cp-toggle-row__hint">{{ isPublic ? 'Показывается пользователям' : 'Скрыт из публичного списка' }}</div>
					</div>
					<button type="button" class="cp-toggle" :class="{ 'cp-toggle--on': isPublic }" :aria-pressed="isPublic" @click="isPublic = !isPublic"></button>
				</div>
			</div>

			<FormMessage v-if="formMessage" :message="formMessage" :message-type="messageType" />
		</template>

		<template #footer>
			<div class="cp-modal-footer">
				<BaseButton variant="outline" text="Отмена" @click="$emit('close')" />
				<BaseButton variant="primary" text="Создать тариф" :loading="isSaving" @click="createTariff" />
			</div>
		</template>
	</Modal>
</template>
