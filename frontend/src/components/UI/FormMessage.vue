<script setup>
const props = defineProps({
	messageType: String,
	message: String,
});
</script>
<template>
	<p class="form-message" :class="props.messageType">{{ props.message }}</p>
</template>
<style scoped>
.form-message {
	padding: 12px 16px;
	border-radius: 8px;
	font-weight: 500;
	margin: 16px 0;
	text-align: center;
	transition: var(--transition);
	background-color: var(--medium-bg);
	border: 1px solid transparent;
}

/* Успешное сообщение */
.form-message.success {
	color: var(--success-color);
	background-color: rgba(46, 204, 113, 0.1);
	border-color: rgba(46, 204, 113, 0.3);
}

/* Ошибка */
.form-message.error {
	color: var(--accent-color);
	background-color: rgba(231, 76, 60, 0.1);
	border-color: rgba(231, 76, 60, 0.3);
}

/* Информационное сообщение */
.form-message.info {
	color: var(--info-color);
	background-color: rgba(155, 89, 182, 0.1);
	border-color: rgba(155, 89, 182, 0.3);
}

/* Предупреждение */
.form-message.warning {
	color: var(--warning-color);
	background-color: rgba(243, 156, 18, 0.1);
	border-color: rgba(243, 156, 18, 0.3);
}
</style>