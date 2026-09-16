<template>
	<div v-if="isOpen" class="modal-overlay" @click.self="handleOverlayClick">
		<div class="modal" :class="sizeClass">
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
	if (props.closeOnOverlayClick) {
		emit('close')
	}
}
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

.modal-header {
	display: flex;
	justify-content: space-between;
	align-items: center;
	margin-bottom: 20px;
}
</style>