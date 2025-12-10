<template>
	<div class="grid grid-cols-1 md:grid-cols-3 gap-6">
		<div class="bg-gray-800 rounded-xl p-6 h-48 flex items-center justify-center">
			<div class="flex flex-col items-center justify-center space-y-4">
				<div class="relative">
					<div class="spinner-outer"></div>
					<div class="spinner-inner"></div>
				</div>
				<p class="text-gray-400 text-sm">Загрузка данных...</p>
			</div>
		</div>
	</div>
</template>

<script setup>
import { ref } from 'vue'
</script>

<style scoped>
/* Кастомные классы для спиннеров */
.spinner-outer {
	width: 64px;
	height: 64px;
	border: 4px solid #374151;
	/* gray-700 */
	border-top: 4px solid #3b82f6;
	/* blue-500 */
	border-radius: 50%;
	animation: spin 1s linear infinite;
}

.spinner-inner {
	position: absolute;
	top: 50%;
	left: 50%;
	transform: translate(-50%, -50%);
	width: 32px;
	height: 32px;
	border: 2px solid #374151;
	/* gray-700 */
	border-right: 2px solid transparent;
	border-radius: 50%;
	animation: spin 1.2s linear infinite;
}

@keyframes spin {
	0% {
		transform: rotate(0deg);
	}

	100% {
		transform: rotate(360deg);
	}
}

/* Для второго спиннера */
@keyframes pulse {

	0%,
	100% {
		opacity: 1;
		transform: scale(1);
	}

	50% {
		opacity: 0.5;
		transform: scale(1.1);
	}
}

.animate-pulse {
	animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

.animate-ping {
	animation: ping 1s cubic-bezier(0, 0, 0.2, 1) infinite;
}

@keyframes ping {

	75%,
	100% {
		transform: scale(2);
		opacity: 0;
	}
}
</style>