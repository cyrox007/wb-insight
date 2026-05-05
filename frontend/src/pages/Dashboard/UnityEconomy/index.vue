<script setup>
import UnityEconomyService from '@/API/Dashboard/UnityEconomyService';
import { onMounted } from 'vue';

onMounted(async () => {
    await UnityEconomyService.get_unity_economy_table()
})

</script>

<template></template>

<style scoped></style>