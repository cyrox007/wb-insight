<script setup>
const props = defineProps({
	messageType: String,
	message: String,
});
</script>
<template>
	<p
		class="form-message"
		:class="props.messageType"
		:role="props.messageType === 'error' ? 'alert' : 'status'"
		:aria-live="props.messageType === 'error' ? 'assertive' : 'polite'"
	>
		{{ props.message }}
	</p>
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
	background-color: rgba(22, 128, 95, 0.08);
	border-color: rgba(22, 128, 95, 0.24);
}

/* Ошибка */
.form-message.error {
	color: var(--accent-color);
	background-color: rgba(200, 59, 85, 0.08);
	border-color: rgba(200, 59, 85, 0.24);
}

/* Информационное сообщение */
.form-message.info {
	color: var(--info-color);
	background-color: rgba(79, 127, 211, 0.08);
	border-color: rgba(79, 127, 211, 0.24);
}

/* Предупреждение */
.form-message.warning {
	color: var(--warning-color);
	background-color: rgba(166, 107, 8, 0.08);
	border-color: rgba(166, 107, 8, 0.24);
}
</style>