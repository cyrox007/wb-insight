<script setup>
import { ref, watch } from 'vue'
import CP_Tariffs from '@/API/ControlPanel/CP_Tariffs'
import Modal from '@/components/UI/Modal.vue'
import TextInput from '@/components/UI/TextInput.vue'
import TextareaInput from '@/components/UI/TextareaInput.vue'
import BaseButton from '@/components/UI/Buttons/BaseButton.vue'
import FormMessage from '@/components/UI/FormMessage.vue'

const props = defineProps({
	isOpen: Boolean,
	currentTariff: Object
})

const emit = defineEmits(['close', 'updated'])
const tariffData = ref({
	name: '',
	description: '',
	price_rub: '',
	is_active: false,
	is_public: false
})
const isSaving = ref(false)
const formMessage = ref('')
const messageType = ref('')

watch(
	() => props.currentTariff,
	(newTariff) => {
		if (!newTariff?.id) return
		tariffData.value = {
			name: newTariff.name || '',
			description: newTariff.description || '',
			price_rub: String(newTariff.price_rub ?? ''),
			is_active: Boolean(newTariff.is_active),
			is_public: Boolean(newTariff.is_public)
		}
		formMessage.value = ''
		messageType.value = ''
	},
	{ immediate: true }
)

async function editTariff() {
	formMessage.value = ''
	messageType.value = ''

	if (!tariffData.value.name.trim()) {
		formMessage.value = 'Название тарифа обязательно.'
		messageType.value = 'error'
		return
	}

	const price = Number(String(tariffData.value.price_rub).replace(',', '.'))
	if (!Number.isFinite(price) || price < 0) {
		formMessage.value = 'Цена должна быть неотрицательным числом.'
		messageType.value = 'error'
		return
	}

	isSaving.value = true
	try {
		const payload = {
			name: tariffData.value.name.trim(),
			description: tariffData.value.description.trim(),
			price_rub: Number(price.toFixed(2)),
			is_active: tariffData.value.is_active,
			is_public: tariffData.value.is_public
		}

		const response = await CP_Tariffs.editTariff(props.currentTariff.id, payload)
		if (response.data?.status !== 'success') {
			throw new Error(response.data?.message || 'Не удалось сохранить тариф')
		}

		emit('updated')
		emit('close')
	} catch (error) {
		console.error('Ошибка редактирования тарифа:', error)
		formMessage.value = error.response?.data?.error?.message || error.message || 'Ошибка при сохранении тарифа'
		messageType.value = 'error'
	} finally {
		isSaving.value = false
	}
}
</script>

<template>
	<Modal :is-open="isOpen" size="large" @close="$emit('close')">
		<template #header>
			<h3 class="cp-modal-title">Редактировать тариф</h3>
		</template>
		<template #body>
			<div class="cp-form-grid">
				<TextInput label="Название тарифа" v-model="tariffData.name" />
				<TextareaInput label="Описание" v-model="tariffData.description" :rows="3" />
				<TextInput v-model="tariffData.price_rub" label="Цена, ₽/мес" type="number" />

				<div class="cp-toggle-row">
					<div class="cp-toggle-row__copy">
						<div class="cp-toggle-row__label">Активный тариф</div>
						<div class="cp-toggle-row__hint">{{ tariffData.is_active ? 'Доступен для подключения' : 'Отключён для подключения' }}</div>
					</div>
					<button type="button" class="cp-toggle" :class="{ 'cp-toggle--on': tariffData.is_active }" :aria-pressed="tariffData.is_active" @click="tariffData.is_active = !tariffData.is_active"></button>
				</div>

				<div class="cp-toggle-row">
					<div class="cp-toggle-row__copy">
						<div class="cp-toggle-row__label">Публичный тариф</div>
						<div class="cp-toggle-row__hint">{{ tariffData.is_public ? 'Показывается пользователям' : 'Скрыт из публичного списка' }}</div>
					</div>
					<button type="button" class="cp-toggle" :class="{ 'cp-toggle--on': tariffData.is_public }" :aria-pressed="tariffData.is_public" @click="tariffData.is_public = !tariffData.is_public"></button>
				</div>
			</div>

			<FormMessage v-if="formMessage" :message="formMessage" :message-type="messageType" />
		</template>
		<template #footer>
			<div class="cp-modal-footer">
				<BaseButton variant="outline" text="Отмена" @click="$emit('close')" />
				<BaseButton variant="primary" text="Сохранить" :loading="isSaving" @click="editTariff" />
			</div>
		</template>
	</Modal>
</template>
