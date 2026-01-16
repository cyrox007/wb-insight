<script setup>
import ControlPanelService from '@/API/ControlPanelService';
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';

const router = useRouter()

const user_count = ref(0); // кол-во зарегестрированных пользователей
const isLoading = ref(false);

onMounted(async () => {
	isLoading.value = true;
	const response = await ControlPanelService.getControlPanel();
	if (response.data) {
		user_count.value = response.data.data.user_count;
	}
	isLoading.value = false;
})
</script>

<template>
	<div class="panel-container">
		<span class="loading-state" v-if="isLoading">Загрузка...</span>
		<div v-else class="stats-content">
			<!-- <h2 class="stats-title">Количество зарегистрированных: {{ user_count }}</h2> -->
			<ul class="stats-links">
				<li>
					<router-link :to="{ name: 'control-panel.users' }" class="stats-link">
						Пользователи
					</router-link>
				</li>
				<li>
					<router-link :to="{ name: 'control-panel.tariffs' }" class="stats-link">
						Тарифы
					</router-link>
				</li>
			</ul>
		</div>
		<RouterView />
	</div>
</template>

<style scoped>
.loading-state,
.stats-content {
	width: 100%;
	text-align: center;
}

.loading-state {
	color: #aaa;
	font-style: italic;
}

.stats-title {
	font-size: 1.35rem;
	font-weight: 600;
	color: var(--text-color);
	margin-bottom: 16px;
}

.stats-links {
	list-style: none;
	padding: 0;
	margin: 0;
	display: flex;
	gap: 5px;
}

.stats-link {
	display: inline-block;
	color: var(--secondary-color);
	text-decoration: underline;
	cursor: pointer;
	font-weight: 500;
	transition: var(--transition);
	padding: 6px 12px;
	border-radius: 6px;
}

.stats-link:hover {
	background-color: var(--hover-bg);
	text-decoration: none;
}

/* Адаптивность */
@media (max-width: 600px) {
	.admin-stats-card {
		padding: 18px;
	}

	.stats-title {
		font-size: 1.15rem;
	}
}
</style>