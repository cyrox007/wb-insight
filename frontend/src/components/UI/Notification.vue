<template>
	<div class="notification" :class="[type, { 'fade-out': !show }]" @click="close">
		<div class="notification-icon">
			<svg v-if="type === 'success'" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor">
				<path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" />
			</svg>
			<svg v-else-if="type === 'error'" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"
				fill="currentColor">
				<path
					d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" />
			</svg>
			<svg v-else-if="type === 'warning'" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"
				fill="currentColor">
				<path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z" />
			</svg>
			<svg v-else xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor">
				<path
					d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z" />
			</svg>
		</div>
		<div class="notification-content">
			<p>{{ message }}</p>
		</div>
	</div>
</template>

<script setup>
import { onMounted, onUnmounted, watch, ref } from 'vue';
const props = defineProps({
	message: { type: String, required: true },
	type: { type: String, default: 'info' }, // 'success', 'error', 'warning', 'info'
	duration: { type: Number, default: 3000 }
});

const emit = defineEmits(['close']);

let timer = null;
const show = ref(true);

onMounted(() => {
	if (props.duration > 0) {
		timer = setTimeout(() => {
			show.value = false;
		}, props.duration);
	}
});
watch(show, (newVal) => {
	if (!newVal) {
		// Ждём окончания анимации перед закрытием
		setTimeout(() => emit('close'), 300);
	}
});
onUnmounted(() => {
	if (timer) {
		clearTimeout(timer);
		timer = null; // ← хорошая практика
	}
});

const close = () => {
	show.value = false;
};
</script>

<style scoped>
.notification {
	position: fixed;
	top: 20px;
	right: 20px;
	display: flex;
	align-items: center;
	gap: 12px;
	padding: 14px 20px;
	border-radius: 8px;
	background-color: var(--card-bg);
	border: 1px solid var(--border-color);
	box-shadow: var(--shadow);
	color: var(--text-color);
	z-index: 10000;
	max-width: 350px;
	opacity: 0;
	transform: translateX(100%);
	transition: opacity 0.3s ease, transform 0.3s ease;
	animation: slideIn 0.3s ease-out forwards;
	cursor: pointer;
}

.notification-icon {
	width: 20px;
	height: 20px;
	display: flex;
	align-items: center;
	justify-content: center;
}

.notification.fade-out {
	opacity: 0 !important;
	transform: translateX(100%) !important;
}

.notification-icon svg {
	width: 18px;
	height: 18px;
}

.notification.success {
	border-left: 4px solid var(--success-color);
}

.notification.error {
	border-left: 4px solid var(--accent-color);
}

.notification.warning {
	border-left: 4px solid var(--warning-color);
}

.notification.info {
	border-left: 4px solid var(--secondary-color);
}

@keyframes slideIn {
	from {
		transform: translateX(100%);
		opacity: 0;
	}

	to {
		transform: translateX(0);
		opacity: 1;
	}
}

@keyframes fadeOut {
	from {
		opacity: 1;
	}

	to {
		opacity: 0;
	}
}
</style>