<script setup>
import { onMounted, ref, watch } from 'vue';
import Modal from '@/components/UI/Modal.vue';
import TextInput from "@/components/UI/TextInput.vue";
import ButtonCancel from '@/components/UI/Buttons/ButtonCancel.vue';
import ButtonPrimary from '@/components/UI/Buttons/ButtonPrimary.vue';
import FormMessage from "@/components/UI/FormMessage.vue";
import CP_Tariffs from '@/API/ControlPanel/CP_Tariffs';
import { useRoute } from 'vue-router';

const props = defineProps({
	isOpen: Boolean,
	limit: Object
})

const emit = defineEmits(['close', 'updated']);

const route = useRoute();

const modalLoadedBtn = ref(false);
const formMessage = ref('');
const msgStatus = ref('');

const limitData = ref({
	limit_type: '',
	limit_value: 0
})

watch(
	() => props.limit,
	(newLimit) => {
		if (newLimit && newLimit.limit_type) {
			limitData.value = {
				limit_type: newLimit.limit_type || '',
				limit_value: newLimit.limit_value ?? 0,
			};
		}
	}
)

const editLimit = async () => {
	// Сбрасываем статус перед началом
	formMessage.value = '';
	msgStatus.value = '';
	modalLoadedBtn.value = true;

	try {
		const payload = {
			limit_value: Number(limitData.value.limit_value) || 0
		};

		const response = await CP_Tariffs.updateLimit(
			route.params.id,
			props.limit.limit_type,
			payload
		);

		if (response.data?.status === 'success') {
			// Успех: показываем сообщение и закрываем через 1 сек
			formMessage.value = 'Лимит успешно обновлён';
			msgStatus.value = 'success';
			emit('updated');

			setTimeout(() => {
				emit('close');
			}, 1000);
		} else {
			throw new Error('Неизвестная ошибка сервера');
		}
	} catch (error) {
		// Ошибка: показываем сообщение, но НЕ закрываем модалку
		formMessage.value = error.response?.data?.error?.message || 'Ошибка при обновлении лимита';
		msgStatus.value = 'error';
	} finally {
		modalLoadedBtn.value = false;
	}
};

</script>
<template>
	<Modal :is-open="isOpen" @close="$emit('close')">
		<template #header>
			<h3>Редактировать лимит</h3>
		</template>
		<template #body>
			<p v-if="props.limit">
				Тип: <strong>{{ props.limit.limit_type }}</strong><br>
				Текущее значение: {{ props.limit.limit_value }}
			</p>

			<TextInput label="Тип лимита" v-model="limitData.limit_type" :disabled="true" />
			<TextInput label="Значение" :type="'number'" v-model="limitData.limit_value" />

		</template>
		<template #footer>
			<FormMessage v-if="formMessage != ''" :message-type="msgStatus" :message="formMessage" />
			<ButtonCancel @click="$emit('close')" :text="'Отмена'" />
			<ButtonPrimary @click="editLimit" :loading="modalLoadedBtn" :text="'Сохранить'" />
		</template>
	</Modal>
</template>
<style></style>