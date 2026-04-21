<template>
    <div class="success-page"></div>
</template>

<script setup>
import PaymentService from '@/API/Dashboard/PaymentService';
import { notify } from '@/composables/notification';
import { onMounted } from 'vue';
import { useRoute } from 'vue-router';

const route = useRoute();

onMounted(async () => {
    console.log(
        route.query.payment_id
    );
    if (route.query.payment_id) {
        const response = await PaymentService.payNow(route.query.payment_id);

        if (response.data.status === 'error') {
            notify.error(response.data.error.message);
            setTimeout(() => {
                location.href = '/dashboard';
            }, 3000);

            return;
        }

        if (response.data.status === 'success') {
            notify.success("Тариф активирован");
            setTimeout(() => {
                location.href = '/dashboard';
            }, 2000);
        }
    }
})
</script>