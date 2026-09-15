<template>
    <main class="payment-page">
        <section class="payment-card">
            <p class="eyebrow">WB Insight · оплата тарифа</p>
            <h1>{{ title }}</h1>
            <p>{{ message }}</p>

            <div v-if="paymentStatus" class="status-row">
                <span>Статус платежа</span>
                <strong>{{ statusLabel }}</strong>
            </div>

            <div class="actions">
                <button v-if="canRetry" type="button" class="primary" :disabled="loading" @click="verifyPayment">
                    {{ loading ? 'Проверяем…' : 'Проверить оплату ещё раз' }}
                </button>
                <router-link to="/dashboard" class="secondary">Вернуться в кабинет</router-link>
            </div>
        </section>
    </main>
</template>

<script setup>
import PaymentService from '@/API/Dashboard/PaymentService';
import { computed, onMounted, ref } from 'vue';
import { useRoute } from 'vue-router';

const route = useRoute();
const loading = ref(true);
const paymentStatus = ref(null);
const provider = ref(null);
const errorMessage = ref(null);

const title = computed(() => {
    if (loading.value) return 'Проверяем оплату';
    if (paymentStatus.value === 'succeeded') return 'Оплата подтверждена';
    if (paymentStatus.value === 'failed' || paymentStatus.value === 'cancelled') return 'Оплата не завершена';
    if (errorMessage.value) return 'Не удалось проверить оплату';
    return 'Ожидаем подтверждение банка';
});

const message = computed(() => {
    if (loading.value) return 'Запрашиваем фактический статус операции у платёжного провайдера.';
    if (paymentStatus.value === 'succeeded') return 'Тариф активирован после server-side подтверждения платежа.';
    if (paymentStatus.value === 'failed') return 'Банк сообщил об отклонении платежа. Вы можете повторить оплату из профиля.';
    if (paymentStatus.value === 'cancelled') return 'Платёж отменён или возвращён. Тариф не изменён.';
    if (errorMessage.value) return errorMessage.value;
    return 'Банк ещё не подтвердил зачисление. Текущий тариф останется активным до подтверждения новой оплаты.';
});

const statusLabel = computed(() => ({
    pending: 'Ожидает подтверждения',
    succeeded: 'Оплачен',
    failed: 'Отклонён',
    cancelled: 'Отменён',
}[paymentStatus.value] || paymentStatus.value));

const canRetry = computed(() => !loading.value && paymentStatus.value === 'pending');

async function verifyPayment() {
    const paymentId = String(route.query.payment_id || '').trim();
    if (!paymentId) {
        loading.value = false;
        errorMessage.value = 'В ссылке возврата отсутствует идентификатор платежа.';
        return;
    }

    loading.value = true;
    errorMessage.value = null;
    try {
        const currentResponse = await PaymentService.getPayment(paymentId);
        const current = currentResponse.data;
        if (current.status === 'error') throw new Error(current.error?.message || 'Платёж не найден');

        paymentStatus.value = current.payment_status;
        provider.value = current.provider;
        if (paymentStatus.value === 'succeeded') return;

        const response = provider.value === 'fake'
            ? await PaymentService.payNow(paymentId)
            : await PaymentService.confirmPayment(paymentId);
        const data = response.data;
        if (data.status === 'error') {
            throw new Error(data.error?.message || 'Не удалось проверить платёж');
        }
        paymentStatus.value = data.payment_status;
    } catch (error) {
        errorMessage.value = error.response?.data?.error?.message || error.message || 'Не удалось проверить статус оплаты';
    } finally {
        loading.value = false;
    }
}

onMounted(verifyPayment);
</script>

<style scoped>
.payment-page {
    min-height: 100vh;
    display: grid;
    place-items: center;
    padding: 32px 20px;
    background: var(--dark-bg, #121212);
    color: var(--text-color, #f4f4f4);
}

.payment-card {
    width: min(560px, 100%);
    padding: 32px;
    border: 1px solid var(--border-color, #343434);
    border-radius: 18px;
    background: var(--medium-bg, #1d1d1d);
}

.eyebrow {
    margin: 0 0 8px;
    font-size: 12px;
    letter-spacing: .08em;
    text-transform: uppercase;
    opacity: .65;
}

h1 {
    margin: 0 0 12px;
}

.payment-card > p:not(.eyebrow) {
    line-height: 1.55;
    opacity: .82;
}

.status-row {
    display: flex;
    justify-content: space-between;
    gap: 16px;
    margin: 24px 0;
    padding: 14px 0;
    border-top: 1px solid var(--border-color, #343434);
    border-bottom: 1px solid var(--border-color, #343434);
}

.actions {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    margin-top: 24px;
}

.primary,
.secondary {
    border-radius: 10px;
    padding: 11px 16px;
    font: inherit;
    text-decoration: none;
    cursor: pointer;
}

.primary {
    border: 0;
    background: var(--secondary-color, #5b8def);
    color: #fff;
}

.primary:disabled {
    opacity: .6;
    cursor: wait;
}

.secondary {
    border: 1px solid var(--border-color, #444);
    color: inherit;
}
</style>
