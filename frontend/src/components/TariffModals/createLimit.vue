<script setup>
import { ref, watch } from "vue";

import CP_Tariffs from "@/API/ControlPanel/CP_Tariffs";

import Modal from "@/components/UI/Modal.vue";
import TextInput from "@/components/UI/TextInput.vue";
import ButtonCancel from '@/components/UI/Buttons/ButtonCancel.vue';
import ButtonPrimary from '@/components/UI/Buttons/ButtonPrimary.vue';
import FormMessage from "@/components/UI/FormMessage.vue";

const props = defineProps({
	isOpen: Boolean,
	tariffId: String,
});

const emit = defineEmits(["close", 'limitCreated']);

const modalLoadedBtn = ref(false);
const msgStatus = ref('');
const formMessage = ref('');

const newLimit = ref({
	limit_type: '',
	limit_value: ''
});

const resetForm = () => {
	newLimit.value = {
		limit_type: '',
		limit_value: ''
	};
	formMessage.value = '';
	msgStatus.value = '';
};

watch(() => props.isOpen, (val) => {
	if (val) {
		resetForm();
	}
});

const createLimit = async () => {
	modalLoadedBtn.value = true;
	formMessage.value = '';
	if (newLimit.value.limit_type === '' || newLimit.value.limit_value === '') {
		formMessage.value = "Заполните все поля";
		msgStatus.value = 'error';
		modalLoadedBtn.value = false;
		return;
	}

	try {
		const response = await CP_Tariffs.createLimit(props.tariffId, { ...newLimit.value });

		if (response.status === 201 && response.data.status === 'success') {
			msgStatus.value = 'success';
			formMessage.value = `Лимит ${newLimit.value.limit_type} успешно добавлен`;
			emit('limitCreated');
			setTimeout(() => {
				modalLoadedBtn.value = false;
				emit('close')
			})
		}
	} catch (error) {
		formMessage.value = error.response.data.error.message;
		msgStatus.value = 'error';
		setTimeout(() => {
			modalLoadedBtn.value = false;
		})
	}
}
</script>
<template>
	<Modal :is-open="isOpen" @close="$emit('close')">
		<template #header>
			<h3>Добавить лимит</h3>
		</template>
		<template #body>
			<TextInput label="Тип лимита" v-model="newLimit.limit_type" />
			<TextInput label="Значение" v-model="newLimit.limit_value" />
		</template>
		<template #footer>
			<FormMessage v-if="formMessage != ''" :message-type="msgStatus" :message="formMessage" />
			<ButtonCancel @click="$emit('close')" :text="'Отмена'" />
			<ButtonPrimary @click="createLimit" :loading="modalLoadedBtn" :text="'Добавить'" />
		</template>
	</Modal>
</template>
<style scoped></style>