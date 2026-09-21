<script setup>
import { ref, watch } from 'vue'
import Modal from '@/components/UI/Modal.vue'
import TextInput from '@/components/UI/TextInput.vue'
import BaseButton from '@/components/UI/Buttons/BaseButton.vue'
import FormMessage from '@/components/UI/FormMessage.vue'
import CP_Tariffs from '@/API/ControlPanel/CP_Tariffs'
import { useRoute } from 'vue-router'

const props = defineProps({
	isOpen: Boolean,
	limit: Object
})

const emit = defineEmits(['close', 'updated'])
const route = useRoute()
const isSaving = ref(false)
const formMessage = ref('')
const msgStatus = ref('')
const limitData = ref({ limit_type: '', limit_value: 0 })
const requiredLimitTypes = new Set(['wb_accounts', 'sync_frequency_hours'])

watch(
	() => props.limit,
	(newLimit) => {
		if (!newLimit?.limit_type) return
		limitData.value = {
			limit_type: newLimit.limit_type,
			limit_value: newLimit.limit_value ?? 0
		}
		formMessage.value = ''
		msgStatus.value = ''
	},
	{ immediate: true }
)

async function editLimit() {
	formMessage.value = ''
	msgStatus.value = ''

	const limitValue = Number(limitData.value.limit_value)
	if (!Number.isFinite(limitValue) || limitValue < 0) {
		formMessage.value = 'Значение лимита должно быть неотрицательным числом.'
		msgStatus.value = 'error'
		return
	}

	if (requiredLimitTypes.has(props.limit?.limit_type) && limitValue < 1) {
		formMessage.value = 'Обязательный runtime-лимит должен быть не меньше 1.'
		msgStatus.value = 'error'
		return
	}

	isSaving.value = true
	try {
		const response = await CP_Tariffs.updateLimit(
			route.params.id,
			props.limit.limit_type,
			{ limit_value: limitValue }
		)

		if (response.data?.status !== 'success') {
			throw new Error(response.data?.message || 'Не удалось обновить лимит')
		}

		emit('updated')
		emit('close')
	} catch (error) {
		formMessage.value = error.response?.data?.error?.message || error.message || 'Ошибка при обновлении лимита'
		msgStatus.value = 'error'
	} finally {
		isSaving.value = false
	}
}
</script>

<template>
	<Modal :is-open="isOpen" @close="$emit('close')">
		<template #header>
			<h3 class="cp-modal-title">Редактировать лимит</h3>
		</template>
		<template #body>
			<div v-if="props.limit" class="cp-modal-meta">
				<strong>{{ props.limit.limit_type }}</strong> · текущее значение {{ props.limit.limit_value }}
			</div>
			<div class="cp-form-grid">
				<TextInput label="Тип лимита" v-model="limitData.limit_type" :disabled="true" />
				<TextInput label="Значение" type="number" v-model="limitData.limit_value" />
			</div>
			<FormMessage v-if="formMessage" :message-type="msgStatus" :message="formMessage" />
		</template>
		<template #footer>
			<div class="cp-modal-footer">
				<BaseButton variant="outline" text="Отмена" @click="$emit('close')" />
				<BaseButton variant="primary" text="Сохранить" :loading="isSaving" @click="editLimit" />
			</div>
		</template>
	</Modal>
</template>
