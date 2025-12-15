<template>
	<BaseButton v-bind="$attrs" :type="type" :disabled="disabled" :loading="loading" :text="text"
		:loading-text="loadingText" :title="title" :size="size" :rounded="rounded" :full-width="fullWidth"
		:icon-left="iconLeft || 'fas fa-sign-in-alt'" variant="primary" @click="$emit('click', $event)">
		<template v-if="$slots.loader" #loader>
			<slot name="loader"></slot>
		</template>

		<template v-if="$slots.iconLeft" #iconLeft>
			<slot name="iconLeft"></slot>
		</template>

		<slot>
			{{ text || 'Войти' }}
		</slot>
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
	loadingText: {
		type: String,
		default: 'Вход...'
	},
	title: {
		type: String,
		default: 'Войти в систему'
	},
	size: {
		type: String,
		default: 'medium'
	},
	rounded: Boolean,
	fullWidth: Boolean,
	iconLeft: String
})

defineEmits(['click'])
</script>