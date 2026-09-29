<template>
	<Teleport to="body">
		<Transition name="modal-motion" appear>
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
		</Transition>
	</Teleport>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'

const props = defineProps({
	isOpen: Boolean,
	size: {
		type: String,
		default: 'medium',
		validator: (value) => ['small', 'medium', 'large', 'xlarge'].includes(value),
	},
	closeOnOverlayClick: {
		type: Boolean,
		default: true,
	},
	closeOnEscape: {
		type: Boolean,
		default: true,
	},
	ariaLabel: {
		type: String,
		default: 'Диалоговое окно',
	},
})

const emit = defineEmits(['close'])
const dialogRef = ref(null)
const previousActiveElement = ref(null)
const bodyScrollLocked = ref(false)

const sizeClass = computed(() => `modal-${props.size}`)

const FOCUSABLE_SELECTOR = [
	'a[href]',
	'button:not([disabled])',
	'input:not([disabled])',
	'select:not([disabled])',
	'textarea:not([disabled])',
	'[tabindex]:not([tabindex="-1"])',
].join(',')

const BODY_LOCK_COUNT_ATTRIBUTE = 'data-wb-modal-lock-count'
const BODY_PREVIOUS_OVERFLOW_ATTRIBUTE = 'data-wb-modal-previous-overflow'

function getFocusableElements() {
	if (!dialogRef.value) return []
	return Array.from(dialogRef.value.querySelectorAll(FOCUSABLE_SELECTOR)).filter(
		(element) => element.getAttribute('aria-hidden') !== 'true'
	)
}

function lockBodyScroll() {
	if (typeof document === 'undefined' || bodyScrollLocked.value) return

	const body = document.body
	const currentCount = Number(body.getAttribute(BODY_LOCK_COUNT_ATTRIBUTE) || 0)

	if (currentCount === 0) {
		body.setAttribute(BODY_PREVIOUS_OVERFLOW_ATTRIBUTE, body.style.overflow || '')
		body.style.overflow = 'hidden'
	}

	body.setAttribute(BODY_LOCK_COUNT_ATTRIBUTE, String(currentCount + 1))
	bodyScrollLocked.value = true
}

function unlockBodyScroll() {
	if (typeof document === 'undefined' || !bodyScrollLocked.value) return

	const body = document.body
	const currentCount = Number(body.getAttribute(BODY_LOCK_COUNT_ATTRIBUTE) || 0)
	const nextCount = Math.max(0, currentCount - 1)

	if (nextCount > 0) {
		body.setAttribute(BODY_LOCK_COUNT_ATTRIBUTE, String(nextCount))
		bodyScrollLocked.value = false
		return
	}

	const previousOverflow = body.getAttribute(BODY_PREVIOUS_OVERFLOW_ATTRIBUTE) || ''
	body.style.overflow = previousOverflow
	body.removeAttribute(BODY_LOCK_COUNT_ATTRIBUTE)
	body.removeAttribute(BODY_PREVIOUS_OVERFLOW_ATTRIBUTE)
	bodyScrollLocked.value = false
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
			unlockBodyScroll()
			restorePreviousFocus()
			return
		}

		previousActiveElement.value = document.activeElement
		lockBodyScroll()
		await nextTick()
		const focusable = getFocusableElements()
		;(focusable[0] || dialogRef.value)?.focus({ preventScroll: true })
	},
	{ immediate: true }
)

onBeforeUnmount(() => {
	unlockBodyScroll()
	restorePreviousFocus()
})
</script>

<style scoped>
.modal-overlay {
	position: fixed;
	inset: 0;
	width: 100vw;
	height: 100dvh;
	box-sizing: border-box;
	padding: 16px;
	background-color: var(--overlay-bg);
	backdrop-filter: blur(4px);
	display: flex;
	align-items: center;
	justify-content: center;
	overflow: auto;
	overscroll-behavior: contain;
	opacity: 1;
	transition:
		opacity 260ms ease,
		backdrop-filter 300ms ease;
	z-index: 10000;
}

.modal {
	background-color: var(--card-bg);
	border: 1px solid var(--border-color);
	border-radius: var(--radius-lg);
	padding: 20px;
	width: min(100%, 500px);
	max-width: none;
	max-height: calc(100dvh - 32px);
	box-sizing: border-box;
	display: flex;
	flex-direction: column;
	overflow: hidden;
	box-shadow: var(--shadow);
	opacity: 1;
	transform: translateY(0) scale(1);
	transform-origin: center;
	transition:
		transform 330ms cubic-bezier(0.22, 1, 0.36, 1),
		opacity 260ms ease;
}

.modal:focus {
	outline: none;
}

.modal-small {
	width: min(100%, 400px);
}

.modal-medium {
	width: min(100%, 500px);
}

.modal-large {
	width: min(100%, 720px);
}

.modal-xlarge {
	width: min(100%, 920px);
}

.modal-motion-enter-from,
.modal-motion-leave-to {
	opacity: 0;
	backdrop-filter: blur(0);
}

.modal-motion-enter-from .modal {
	opacity: 0;
	transform: translateY(14px) scale(0.975);
}

.modal-motion-leave-to .modal {
	opacity: 0;
	transform: translateY(8px) scale(0.985);
}

.modal-motion-enter-active .modal {
	will-change: transform, opacity;
}

.modal-motion-leave-active .modal {
	transition-duration: 230ms;
}

@media (prefers-reduced-motion: reduce) {
	.modal-overlay,
	.modal {
		transition: none;
	}

	.modal-motion-enter-from .modal,
	.modal-motion-leave-to .modal {
		transform: none;
	}
}

.modal-body {
	min-height: 0;
	overflow-y: auto;
	overscroll-behavior: contain;
}

.modal-footer {
	flex: 0 0 auto;
}

.modal-header {
	display: flex;
	justify-content: space-between;
	align-items: center;
	margin-bottom: 20px;
}

@media (max-width: 640px) {
	.modal-overlay {
		align-items: flex-start;
		padding: 12px;
	}

	.modal {
		width: 100%;
		max-width: 100%;
		max-height: calc(100dvh - 24px);
		margin-block: auto;
		padding: 16px;
	}
}
</style>
