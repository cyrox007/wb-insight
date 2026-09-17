<template>
	<div class="form-group">
		<label v-if="label" class="form-label" :for="textareaId">{{ label }}</label>

		<textarea
			:id="textareaId"
			class="form-textarea"
			:value="modelValue"
			@input="$emit('update:modelValue', $event.target.value)"
			:placeholder="placeholder"
			:disabled="disabled"
			:rows="rows"
			:aria-invalid="error ? 'true' : undefined"
			:aria-describedby="error ? errorId : undefined"
		/>

		<div v-if="error" :id="errorId" class="form-error" role="alert">
			{{ error }}
		</div>
	</div>
</template>

<script setup>
import { computed, useId } from 'vue'

const generatedId = useId()
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
	id: {
		type: String,
		default: ''
	},
	disabled: {
		type: Boolean,
		default: false
	},
	rows: {
		type: Number,
		default: 4
	},
	error: {
		type: String,
		default: ''
	}
})

const textareaId = computed(() => props.id || `textarea-${generatedId}`)
const errorId = computed(() => `${textareaId.value}-error`)

defineEmits(['update:modelValue'])
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

.form-textarea {
	width: 100%;
	padding: 10px;
	border: 1px solid var(--border-color);
	border-radius: 6px;
	background-color: var(--medium-bg);
	color: var(--text-color);
	resize: vertical;
	font-family: monospace;
}

.form-textarea:focus {
	outline: none;
	border-color: var(--secondary-color);
}

.form-textarea:disabled {
	background-color: var(--dark-bg);
	color: #666;
	cursor: not-allowed;
	opacity: 0.7;
}

.form-error {
	margin-top: 4px;
	font-size: 0.8rem;
	color: var(--accent-color);
}
</style>