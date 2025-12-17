<template>
	<div class="panel-container">
		<span v-if="isLoading">Загрузка...</span>
		<span v-else>Кол-во зарегестрированных: {{ user_count }}</span>
		<RouterView />
	</div>
</template>

<script setup>
import ControlPanelService from '@/API/ControlPanelService';
import { ref, onMounted } from 'vue';

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