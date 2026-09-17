<template>
	<div
		v-if="isOpen"
		class="modal-overlay"
		@click.self="handleOverlayClick"
		@keydown="handleKeydown"
	>
		<div
			ref="dialogRef"
			class="modal"
			:class="sizeClass"
			role="dialog"
			aria-modal="true"
			:aria-label="ariaLabel"
			tabindex="-1"
		>
			<slot name="header"></slot>
			<div class="modal-body">
				<slot name="body"></slot>
			</div>
			<div v-if="$slots.footer" class="modal-footer">
				<slot name="footer"></slot>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'

const props = defineProps({
	isOpen: Boolean,
	size: {
		type: String,
		default: 'medium',
		validator: (value) => ['small', 'medium', 'large', 'xlarge'].includes(value)
	},
	closeOnOverlayClick: {
		type: Boolean,
		default: true
	},
	closeOnEscape: {
		type: Boolean,
		default: true
	},
	ariaLabel: {
		type: String,
		default: 'Диалоговое окно'
	}
})

const emit = defineEmits(['close'])
const dialogRef = ref(null)
const previousActiveElement = ref(null)

const sizeClass = computed(() => `modal-${props.size}`)

const FOCUSABLE_SELECTOR = [
	'a[href]',
	'button:not([disabled])',
	'input:not([disabled])',
	'select:not([disabled])',
	'textarea:not([disabled])',
	'[tabindex]:not([tabindex="-1"])'
].join(',')

function getFocusableElements() {
	if (!dialogRef.value) return []
	return Array.from(dialogRef.value.querySelectorAll(FOCUSABLE_SELECTOR)).filter(
		(element) => element.getAttribute('aria-hidden') !== 'true'
	)
}

function restorePreviousFocus() {
	const element = previousActiveElement.value
	previousActiveElement.value = null
	if (element && typeof element.focus === 'function' && element.isConnected) {
		nextTick(() => element.focus({ preventScroll: true }))
	}
}

function requestClose() {
	emit('close')
}

function handleOverlayClick() {
	if (props.closeOnOverlayClick) requestClose()
}

function handleKeydown(event) {
	if (event.key === 'Escape') {
		if (!props.closeOnEscape) return
		event.preventDefault()
		requestClose()
		return
	}

	if (event.key !== 'Tab') return

	const focusable = getFocusableElements()
	if (!focusable.length) {
		event.preventDefault()
		dialogRef.value?.focus({ preventScroll: true })
		return
	}

	const first = focusable[0]
	const last = focusable[focusable.length - 1]
	const active = document.activeElement

	if (event.shiftKey && (active === first || active === dialogRef.value)) {
		event.preventDefault()
		last.focus()
	} else if (!event.shiftKey && active === last) {
		event.preventDefault()
		first.focus()
	}
}

watch(
	() => props.isOpen,
	async (isOpen) => {
		if (!isOpen) {
			restorePreviousFocus()
			return
		}

		previousActiveElement.value = document.activeElement
		await nextTick()
		const focusable = getFocusableElements()
		;(focusable[0] || dialogRef.value)?.focus({ preventScroll: true })
	},
	{ immediate: true }
)

onBeforeUnmount(restorePreviousFocus)
</script>

<style scoped>
.modal-overlay {
	position: fixed;
	top: 0;
	left: 0;
	right: 0;
	bottom: 0;
	background-color: rgba(0, 0, 0, 0.7);
	display: flex;
	align-items: center;
	justify-content: center;
	z-index: 1000;
}

.modal {
	background-color: var(--card-bg);
	border-radius: 8px;
	padding: 20px;
	width: 500px;
	max-width: 90%;
	box-shadow: var(--shadow);
}

.modal:focus {
	outline: none;
}

.modal-header {
	display: flex;
	justify-content: space-between;
	align-items: center;
	margin-bottom: 20px;
}
</style>
