<template>
    <label class="account-filter">
        <span class="account-filter__label">Кабинет WB</span>
        <select class="account-filter__select" :value="selectedTokenId" @change="onChange">
            <option value="">Все кабинеты</option>
            <option v-for="account in accounts" :key="account.id" :value="account.id">
                {{ account.label || 'Wildberries' }} · {{ account.id.slice(0, 8) }}
            </option>
        </select>
    </label>
</template>

<script setup>
import { onMounted } from 'vue'
import { useDashboardAccount } from '@/composables/dashboardAccount.js'

const emit = defineEmits(['change'])
const {
    accounts,
    selectedTokenId,
    loadAccounts,
    setSelectedTokenId,
} = useDashboardAccount()

const onChange = (event) => {
    setSelectedTokenId(event.target.value)
    emit('change', selectedTokenId.value)
}

onMounted(async () => {
    await loadAccounts()
})
</script>

<style scoped>
.account-filter {
    display: flex;
    flex-direction: column;
    gap: 6px;
    min-width: 210px;
}

.account-filter__label {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-color);
    opacity: 0.72;
}

.account-filter__select {
    min-height: 38px;
    padding: 8px 10px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background: var(--light-bg);
    color: var(--text-color);
    font: inherit;
}

.account-filter__select:focus {
    outline: none;
    border-color: var(--secondary-color);
}
</style>
