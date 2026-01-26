<script setup>
import { ref } from 'vue';
import Modal from '@/components/UI/Modal.vue';
import ButtonCancel from '@/components/UI/Buttons/ButtonCancel.vue';
import ButtonPrimary from '@/components/UI/Buttons/ButtonPrimary.vue';
import TextInput from '@/components/UI/TextInput.vue';
import FormMessage from '@/components/UI/FormMessage.vue';

const props = defineProps({
	isOpen: Boolean,
	userId: String,
});

defineEmits(['close', 'updated']);

const modalLoadedBtn = ref(false);
const msg = ref('');
const msgType = ref('');

const newPassword = ref('');
const repeatPassword = ref('');

const changePassword = async () => {
	modalLoadedBtn.value = true;
	msg.value = '';
	msgType.value = '';

	try {
		// Валидация
		if (!newPassword.value.trim()) {
			throw new Error('Пароль не может быть пустым');
		}
		if (newPassword.value !== repeatPassword.value) {
			throw new Error('Пароли не совпадают');
		}
		if (newPassword.value.length < 8) {
			throw new Error('Пароль должен содержать минимум 8 символов');
		}

		// TODO: вызов API
		// const response = await CP_Users.changePassword(props.userId, {
		//   new_password: newPassword.value
		// });

		// Имитация успешного запроса
		setTimeout(() => {
			msg.value = 'Пароль успешно изменён';
			msgType.value = 'success';

			// Закрываем через 1 секунду
			setTimeout(() => {
				emit('updated'); // ← уведомляем родителя
				emit('close');
			}, 1000);
		}, 500);

	} catch (error) {
		msg.value = error.message || 'Ошибка при смене пароля';
		msgType.value = 'error';
	} finally {
		modalLoadedBtn.value = false;
	}
};
</script>
<template>
	<Modal :is-open="isOpen" @close="$emit('close')">
		<template #header>
			<h3>Сменить пароль</h3>
		</template>
		<template #body>
			<TextInput label="Новый пароль" v-model="newPassword" placeholder="Введите новый пароль" type="password" />
			<TextInput label="Повторите пароль" v-model="repeatPassword" placeholder="Повторите новый пароль"
				type="password" />
		</template>
		<template #footer>
			<FormMessage :message-type="msgType" :message="msg" v-if="msg" />
			<ButtonCancel @click="$emit('close')" text="Отмена" />
			<ButtonPrimary @click="changePassword" :loading="modalLoadedBtn" text="Сохранить" />
		</template>
	</Modal>
</template>
<style scoped>
:deep(.form-group) {
	margin-bottom: 16px;
}
</style>