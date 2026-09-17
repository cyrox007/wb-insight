<template>
	<button
		:type="type"
		:class="buttonClasses"
		:disabled="disabled || loading"
		:aria-busy="loading ? 'true' : undefined"
		@click="handleClick"
		:title="title"
	>
		<div v-if="loading" class="button-loader">
			<slot name="loader">
				<SpinnerButtonSmall />
			</slot>
		</div>

		<!-- <div v-if="iconLeft || $slots.iconLeft" class="button-icon-left">
			<slot name="iconLeft">
				<i v-if="iconLeft" :class="iconLeft"></i>
			</slot>
		</div> -->

		<span class="button-text">
			<slot>
				{{ loading ? (loadingText || text) : text }}
			</slot>
		</span>

		<div v-if="iconRight || $slots.iconRight" class="button-icon-right">
			<slot name="iconRight">
				<i v-if="iconRight" :class="iconRight"></i>
			</slot>
		</div>
	</button>
</template>

<script setup>
import { computed } from 'vue'
import SpinnerButtonSmall from '@/components/Loaders/SpinnerButtonSmall.vue'

const props = defineProps({
	// Основные
	type: {
		type: String,
		default: 'button',
		validator: (value) => ['button', 'submit', 'reset'].includes(value)
	},
	disabled: Boolean,
	loading: Boolean,

	// Текст
	text: String,
	loadingText: String,
	title: String,

	// Стили
	variant: {
		type: String,
		default: 'primary',
		validator: (value) => [
			'primary', 'secondary', 'success', 'danger',
			'warning', 'info', 'outline', 'ghost', 'link'
		].includes(value)
	},
	size: {
		type: String,
		default: 'medium',
		validator: (value) => ['small', 'medium', 'large', 'xlarge'].includes(value)
	},
	rounded: Boolean,
	fullWidth: Boolean,

	// Иконки
	iconLeft: {
		type: String,
		default: ''
	},
	iconRight: String
})

const emit = defineEmits(['click'])

const buttonClasses = computed(() => [
	'base-button',
	`btn-${props.variant}`,
	`btn-${props.size}`,
	{
		'btn-rounded': props.rounded,
		'btn-full-width': props.fullWidth,
		'btn-loading': props.loading,
		'btn-disabled': props.disabled
	}
])

const handleClick = (event) => {
	if (!props.disabled && !props.loading) {
		emit('click', event)
	}
}
</script>

<style scoped>
.base-button {
	display: inline-flex;
	align-items: center;
	justify-content: center;
	gap: 0.5rem;
	font-weight: 500;
	line-height: 1.5;
	text-align: center;
	text-decoration: none;
	vertical-align: middle;
	cursor: pointer;
	user-select: none;
	border: 1px solid transparent;
	border-radius: 0.375rem;
	transition: all 0.2s ease-in-out;
	position: relative;
}

/* Размеры */
.btn-small {
	padding: 0.375rem 0.75rem;
	font-size: 0.875rem;
	min-height: 2rem;
}

.btn-medium {
	padding: 0.5rem 1rem;
	font-size: 1rem;
	min-height: 2.5rem;
}

.btn-large {
	padding: 0.75rem 1.5rem;
	font-size: 1.125rem;
	min-height: 3rem;
}

.btn-xlarge {
	padding: 1rem 2rem;
	font-size: 1.25rem;
	min-height: 3.5rem;
}

/* Варианты */
.btn-primary {
	background-color: var(--secondary-color);
	border-color: var(--secondary-color);
	color: white;
}

.btn-primary:hover:not(:disabled):not(.btn-loading) {
	background-color: #2980b9;
	border-color: #2980b9;
}

.btn-secondary {
	background-color: #6c757d;
	border-color: #6c757d;
	color: white;
}

.btn-secondary:hover:not(:disabled):not(.btn-loading) {
	background-color: #5a6268;
	border-color: #545b62;
}

.btn-success {
	background-color: var(--success-color);
	border-color: var(--success-color);
	color: white;
}

.btn-success:hover:not(:disabled):not(.btn-loading) {
	background-color: #27ae60;
	border-color: #229954;
}

.btn-danger {
	background-color: var(--accent-color);
	border-color: var(--accent-color);
	color: white;
}

.btn-danger:hover:not(:disabled):not(.btn-loading) {
	background-color: #c0392b;
	border-color: #b03a2e;
}

.btn-outline {
	background-color: transparent;
	border-color: var(--border-color);
	color: var(--text-color);
}

.btn-outline:hover:not(:disabled):not(.btn-loading) {
	background-color: var(--hover-bg);
	border-color: var(--secondary-color);
}

.btn-ghost {
	background-color: transparent;
	border-color: transparent;
	color: var(--text-color);
}

.btn-ghost:hover:not(:disabled):not(.btn-loading) {
	background-color: var(--hover-bg);
}

.btn-link {
	background-color: transparent;
	border-color: transparent;
	color: var(--secondary-color);
	text-decoration: underline;
}

.btn-link:hover:not(:disabled):not(.btn-loading) {
	text-decoration: none;
	color: #2980b9;
}

/* Модификаторы */
.btn-rounded {
	border-radius: 2rem;
}

.btn-full-width {
	width: 100%;
}

/* Состояния */
.btn-loading {
	cursor: wait;
	opacity: 0.8;
}

.btn-disabled,
.base-button:disabled {
	opacity: 0.65;
	cursor: not-allowed;
	pointer-events: none;
}

/* Внутренние элементы */
.button-loader {
	display: flex;
	align-items: center;
	margin-right: 0.5rem;
}

.button-text {
	display: inline-block;
	transition: opacity 0.2s;
}

.btn-loading .button-text {
	opacity: 0.8;
}

.button-icon-left,
.button-icon-right {
	display: flex;
	align-items: center;
}

.button-icon-left {
	margin-right: 0.25rem;
}

.button-icon-right {
	margin-left: 0.25rem;
}

/* Focus стили */
.base-button:focus {
	outline: 2px solid var(--secondary-color);
	outline-offset: 2px;
}

.base-button:focus:not(:focus-visible) {
	outline: none;
}
</style>
