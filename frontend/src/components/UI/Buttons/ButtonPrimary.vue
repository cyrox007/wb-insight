<template>
	<BaseButton v-bind="$attrs" :type="type" :disabled="disabled" :loading="loading" :text="text"
		:loading-text="loadingText" :title="title" :size="size" :rounded="rounded" :full-width="fullWidth"
		:icon-left="iconLeft" :icon-right="iconRight" variant="primary" @click="$emit('click', $event)">
		<template v-if="$slots.loader" #loader>
			<slot name="loader"></slot>
		</template>

		<template v-if="$slots.iconLeft" #iconLeft>
			<slot name="iconLeft"></slot>
		</template>

		<slot>
			{{ text }}
		</slot>

		<template v-if="$slots.iconRight" #iconRight>
			<slot name="iconRight"></slot>
		</template>
	</BaseButton>
</template>

<script setup>
import BaseButton from './BaseButton.vue'

defineProps({
	type: {
		type: String,
		default: 'button'
	},
	disabled: Boolean,
	loading: Boolean,
	text: String,
	loadingText: String,
	title: String,
	size: {
		type: String,
		default: 'medium'
	},
	rounded: Boolean,
	fullWidth: Boolean,
	iconLeft: String,
	iconRight: String
})

defineEmits(['click'])
</script>