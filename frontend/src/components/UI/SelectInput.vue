<template>
	<div class="ui-field">
		<label v-if="label" class="ui-label">{{ label }}</label>

		<select :value="modelValue" @change="$emit('update:modelValue', $event.target.value)" :disabled="disabled"
			class="ui-select">
			<option v-for="opt in options" :key="opt.value" :value="opt.value">
				{{ opt.label }}
			</option>
		</select>

		<div v-if="error" class="ui-error">{{ error }}</div>
	</div>
</template>

<script setup>
defineProps({
	modelValue: String,
	options: Array,
	label: String,
	disabled: Boolean,
	error: String
})
</script>

<style scoped>
.ui-field {
	display: flex;
	flex-direction: column;
	gap: 4px;
}

.ui-label {
	font-size: 13px;
	color: var(--text-muted);
}

.ui-select {
	padding: 10px 12px;
	border-radius: 8px;
	border: 1px solid var(--border-color);
	font-size: 14px;
	background: var(--medium-bg);
	color: var(--text-color);
}

.ui-select:disabled {
	background: var(--dark-bg);
	cursor: not-allowed;
}

.ui-error {
	color: var(--danger-color);
	font-size: 12px;
}
</style>