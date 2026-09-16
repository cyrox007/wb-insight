<template>
	<div v-if="isOpen" class="modal-overlay" @click.self="handleOverlayClick">
		<div class="modal" :class="sizeClass" role="dialog" aria-modal="true">
			<div class="modal-heading">
				<slot name="header"></slot>
			</div>
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
import { computed } from 'vue'

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
	}
})

const emit = defineEmits(['close'])
const sizeClass = computed(() => `modal-${props.size}`)

const handleOverlayClick = () => {
	if (props.closeOnOverlayClick) emit('close')
}
</script>

<style scoped>
.modal-overlay {
	position: fixed;
	inset: 0;
	z-index: 1000;
	display: flex;
	align-items: center;
	justify-content: center;
	padding: 16px;
	background: rgba(3, 7, 18, 0.76);
	backdrop-filter: blur(4px);
}

.modal {
	width: min(100%, 520px);
	max-height: calc(100vh - 32px);
	overflow-y: auto;
	padding: 22px;
	border: 1px solid var(--border-color);
	border-radius: var(--radius-lg);
	background: var(--card-bg-elevated);
	box-shadow: 0 24px 70px rgba(0, 0, 0, 0.42);
}

.modal-small {
	width: min(100%, 400px);
}

.modal-medium {
	width: min(100%, 520px);
}

.modal-large {
	width: min(100%, 720px);
}

.modal-xlarge {
	width: min(100%, 920px);
}

.modal-heading {
	color: var(--text-color);
}

.modal-body {
	margin-top: 16px;
}

.modal-footer {
	display: flex;
	justify-content: flex-end;
	gap: 8px;
	margin-top: 20px;
	padding-top: 16px;
	border-top: 1px solid var(--border-color);
}

@media (max-width: 560px) {
	.modal-overlay {
		align-items: flex-end;
		padding: 8px;
	}

	.modal {
		width: 100%;
		max-height: calc(100vh - 16px);
		padding: 18px;
		border-radius: var(--radius-lg) var(--radius-lg) var(--radius-sm) var(--radius-sm);
	}
}
</style>
