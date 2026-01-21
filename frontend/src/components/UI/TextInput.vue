<template>
	<div class="form-group">
		<label class="form-label">{{ label }}</label>
		<input class="form-input" :type="type" :value="modelValue"
			@input="$emit('update:modelValue', $event.target.value)" :placeholder="placeholder" :disabled="disabled">
	</div>
</template>

<script setup>
import { ref, defineProps } from 'vue'

const props = defineProps({
	modelValue: {
		type: String,
		default: ''
	},
	placeholder: {
		type: String,
		default: ''
	},
	label: {
		type: String,
		default: ''
	},
	type: {
		type: String,
		default: 'text'
	},
	disabled: {
		type: Boolean,
		default: false
	}
});
</script>

<style scoped>
.form-group {
	margin-bottom: 15px;
}

.form-label {
	display: block;
	margin-bottom: 5px;
	font-size: 14px;
}

.form-input {
	width: 100%;
	padding: 10px;
	border: 1px solid var(--border-color);
	border-radius: 6px;
	background-color: var(--medium-bg);
	color: var(--text-color);
}

.form-input:focus {
	outline: none;
	border-color: var(--secondary-color);
}

.form-input:disabled {
	background-color: var(--dark-bg);
	/* Более тёмный фон */
	color: #666;
	/* Приглушённый текст */
	cursor: not-allowed;
	opacity: 0.7;
}

.form-input:disabled::placeholder {
	color: #555;
}
</style>