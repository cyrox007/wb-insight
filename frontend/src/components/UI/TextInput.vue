<template>
	<div class="form-group">
		<label class="form-label">{{ label }}</label>
		<input class="form-input" :type="type" :value="modelValue"
			@input="$emit('update:modelValue', $event.target.value)" :placeholder="placeholder">
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
</style>