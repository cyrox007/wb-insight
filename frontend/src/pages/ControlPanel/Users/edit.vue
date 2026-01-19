<script setup>
import CP_Users from '@/API/ControlPanel/CP_Users';
import { ref, onMounted } from 'vue';
import { useRoute } from 'vue-router';

const route = useRoute();

const targetUser = ref(null)

onMounted(async () => {
	const result = await CP_Users.getUserByUuid(route.params.id)
	console.log(result.data);

})
</script>
<template>

</template>
<style scoped></style>