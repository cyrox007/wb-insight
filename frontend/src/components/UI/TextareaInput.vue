<template>
	<div class="form-group">
		<label v-if="label" class="form-label">{{ label }}</label>

		<textarea class="form-textarea" :value="modelValue" @input="$emit('update:modelValue', $event.target.value)"
			:placeholder="placeholder" :disabled="disabled" :rows="rows" />

		<div v-if="error" class="form-error">
			{{ error }}
		</div>
	</div>
</template>

<script setup>
defineProps({
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