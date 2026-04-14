<template>
	<div class="stats-loading">
		<div class="loading-spinner"></div>
		<p class="loading-text">Загрузка показателей...</p>
	</div>
</template>

<style scoped>
/* Состояние загрузки */
.stats-loading {
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	padding: 20px;
	color: #888;
}

.loading-spinner {
	width: 24px;
	height: 24px;
	border: 3px solid rgba(255, 255, 255, 0.3);
	border-radius: 50%;
	border-top-color: #fff;
	animation: spin 1s linear infinite;
	margin-bottom: 12px;
}

@keyframes spin {
	to {
		transform: rotate(360deg);
	}
}

.loading-text {
	font-size: 14px;
	color: #888;
}
</style>