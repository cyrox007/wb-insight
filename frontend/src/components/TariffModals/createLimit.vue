<script setup>
import { ref, watch } from 'vue'
import CP_Tariffs from '@/API/ControlPanel/CP_Tariffs'
import Modal from '@/components/UI/Modal.vue'
import TextInput from '@/components/UI/TextInput.vue'
import BaseButton from '@/components/UI/Buttons/BaseButton.vue'
import FormMessage from '@/components/UI/FormMessage.vue'

const props = defineProps({
	isOpen: Boolean,
	tariffId: String
})

const emit = defineEmits(['close', 'limitCreated'])
const isSaving = ref(false)
const msgStatus = ref('')
const formMessage = ref('')
const newLimit = ref({ limit_type: '', limit_value: '' })
const requiredLimitTypes = new Set(['wb_accounts', 'sync_frequency_hours'])

function resetForm() {
	newLimit.value = { limit_type: '', limit_value: '' }
	formMessage.value = ''
	msgStatus.value = ''
}

watch(() => props.isOpen, (isOpen) => {
	if (isOpen) resetForm()
})

async function createLimit() {
	formMessage.value = ''
	msgStatus.value = ''

	if (!newLimit.value.limit_type.trim() || String(newLimit.value.limit_value).trim() === '') {
		formMessage.value = 'Заполните тип и значение лимита.'
		msgStatus.value = 'error'
		return
	}

	const limitValue = Number(newLimit.value.limit_value)
	if (!Number.isFinite(limitValue) || limitValue < 0) {
		formMessage.value = 'Значение лимита должно быть неотрицательным числом.'
		msgStatus.value = 'error'
		return
	}

	if (requiredLimitTypes.has(newLimit.value.limit_type.trim()) && limitValue < 1) {
		formMessage.value = 'Обязательный runtime-лимит должен быть не меньше 1.'
		msgStatus.value = 'error'
		return
	}

	isSaving.value = true
	try {
		const response = await CP_Tariffs.createLimit(props.tariffId, {
			limit_type: newLimit.value.limit_type.trim(),
			limit_value: limitValue
		})

		if (response.status !== 201 || response.data?.status !== 'success') {
			throw new Error(response.data?.message || 'Не удалось добавить лимит')
		}

		emit('limitCreated')
		emit('close')
	} catch (error) {
		formMessage.value = error.response?.data?.error?.message || error.message || 'Ошибка при добавлении лимита'
		msgStatus.value = 'error'
	} finally {
		isSaving.value = false
	}
}
</script>

<template>
	<Modal :is-open="isOpen" @close="$emit('close')">
		<template #header>
			<h3 class="cp-modal-title">Добавить лимит</h3>
		</template>
		<template #body>
			<div class="cp-form-grid">
				<TextInput label="Тип лимита" v-model="newLimit.limit_type" placeholder="Например: wb_accounts" />
				<TextInput label="Значение" v-model="newLimit.limit_value" type="number" placeholder="0" />
				<p class="cp-muted">Тип используется как системный ключ. Для существующих типов придерживайтесь текущих кодов тарифа.</p>
			</div>
			<FormMessage v-if="formMessage" :message-type="msgStatus" :message="formMessage" />
		</template>
		<template #footer>
			<div class="cp-modal-footer">
				<BaseButton variant="outline" text="Отмена" @click="$emit('close')" />
				<BaseButton variant="primary" text="Добавить" :loading="isSaving" @click="createLimit" />
			</div>
		</template>
	</Modal>
</template>
