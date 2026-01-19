<script setup>
import ControlPanelService from '@/API/ControlPanel/ControlPanelService';
import { ref, onMounted } from 'vue';
import { useRoute } from 'vue-router';

const route = useRoute();

const targetUser = ref(null)

onMounted(async () => {
	const result = await ControlPanelService.getUserByUuid(route.params.id)
	console.log(result.data);

})
</script>
<template>

</template>
<style scoped></style>