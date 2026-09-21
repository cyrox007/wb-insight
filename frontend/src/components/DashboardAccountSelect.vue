<template>
    <div class="account-tools">
        <label class="field account-filter">
            <span class="field__label">Кабинет</span>
            <select class="field__control" :value="selectedTokenId" :disabled="accountsLoading || !accounts.length" @change="onChange">
                <option v-if="accountsLoading" value="">Загружаем кабинеты…</option>
                <option v-else-if="!accounts.length" value="">Нет доступных кабинетов</option>
                <option v-else value="">Все кабинеты WB</option>
                <option v-for="account in accounts" :key="account.id" :value="account.id">
                    {{ account.label || 'Wildberries' }} · {{ account.id.slice(0, 8) }}
                </option>
            </select>
        </label>

        <form
            v-if="route.name === 'dashboard.home' && selectedTokenId"
            class="plan-editor"
            @submit.prevent="savePlan"
        >
            <label class="field plan-editor__field">
                <span class="field__label">План месяца</span>
                <div class="money-input">
                    <input
                        v-model="planTarget"
                        class="field__control field__control--number"
                        type="number"
                        min="0.01"
                        step="0.01"
                        placeholder="500000"
                        :disabled="isSaving"
                    />
                    <span>₽</span>
                </div>
            </label>
            <button class="control-button control-button--primary" type="submit" :disabled="isSaving || !planTarget">
                Сохранить
            </button>
            <button class="control-button" type="button" :disabled="isSaving" @click="removePlan">
                Сбросить
            </button>
        </form>

        <p v-else-if="route.name === 'dashboard.home' && accounts.length" class="plan-hint">
            Выберите один кабинет, чтобы задать месячный план.
        </p>
    </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import DashboardService from '@/API/Dashboard/DashboardService.js'
import { notify } from '@/composables/notification'
import { useDashboardAccount } from '@/composables/dashboardAccount.js'

const emit = defineEmits(['change'])
const route = useRoute()
const planTarget = ref('')
const isSaving = ref(false)
const {
    accounts,
    accountsLoading,
    selectedTokenId,
    loadAccounts,
    setSelectedTokenId,
    refreshDashboard,
} = useDashboardAccount()

const onChange = (event) => {
    planTarget.value = ''
    setSelectedTokenId(event.target.value)
    emit('change', selectedTokenId.value)
}

const savePlan = async () => {
    const value = Number(planTarget.value)
    if (!Number.isFinite(value) || value <= 0) {
        notify.error('План должен быть больше нуля', 3000)
        return
    }

    isSaving.value = true
    try {
        const response = await DashboardService.set_monthly_plan(value)
        if (response.data?.status === 'error') {
            notify.error(response.data.error?.message || 'Не удалось сохранить план', 3000)
            return
        }
        planTarget.value = ''
        notify.success('План текущего месяца сохранён', 2500)
        refreshDashboard()
    } catch (error) {
        notify.error(error.response?.data?.error?.message || 'Не удалось сохранить план', 3000)
    } finally {
        isSaving.value = false
    }
}

const removePlan = async () => {
    isSaving.value = true
    try {
        const response = await DashboardService.delete_monthly_plan()
        if (response.data?.status === 'error') {
            notify.error(response.data.error?.message || 'Не удалось сбросить план', 3000)
            return
        }
        planTarget.value = ''
        notify.success('План текущего месяца сброшен', 2500)
        refreshDashboard()
    } catch (error) {
        notify.error(error.response?.data?.error?.message || 'Не удалось сбросить план', 3000)
    } finally {
        isSaving.value = false
    }
}

onMounted(loadAccounts)
</script>

<style scoped>
.account-tools {
    display: grid;
    grid-template-columns: minmax(205px, 230px) auto;
    align-items: end;
    justify-content: end;
    gap: 8px 12px;
}

.field {
    display: flex;
    flex-direction: column;
    gap: 5px;
}

.account-filter {
    min-width: 205px;
}

.plan-editor {
    display: flex;
    align-items: flex-end;
    gap: 6px;
}

.plan-editor__field {
    min-width: 165px;
}

.field__label {
    color: var(--text-muted);
    font-size: 11px;
    font-weight: 650;
    letter-spacing: 0.01em;
}

.field__control {
    min-height: 36px;
    padding: 7px 10px;
    border: 1px solid var(--border-color);
    border-radius: 8px;
    background: var(--light-bg);
    color: var(--text-color);
}

.field__control:hover {
    border-color: var(--border-strong);
}

.money-input {
    position: relative;
}

.money-input .field__control {
    width: 100%;
    padding-right: 28px;
}

.money-input span {
    position: absolute;
    top: 50%;
    right: 10px;
    transform: translateY(-50%);
    color: var(--text-subtle);
    pointer-events: none;
}

.control-button {
    min-height: 36px;
    padding: 7px 11px;
    border: 1px solid var(--border-color);
    border-radius: 8px;
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    transition: background var(--transition), color var(--transition), border-color var(--transition);
}

.control-button:hover:not(:disabled) {
    border-color: var(--border-strong);
    background: var(--hover-bg);
    color: var(--text-color);
}

.control-button--primary {
    border-color: rgba(99, 91, 255, 0.32);
    background: rgba(99, 91, 255, 0.09);
    color: #5b52d6;
}

.control-button:disabled {
    opacity: 0.45;
    cursor: default;
}

.plan-hint {
    max-width: 210px;
    margin: 0 0 3px;
    color: var(--text-subtle);
    font-size: 11px;
    line-height: 1.35;
}

@media (max-width: 1100px) {
    .account-tools {
        grid-template-columns: minmax(205px, 1fr);
        justify-content: stretch;
    }

    .plan-editor {
        width: 100%;
        justify-content: flex-start;
    }

    .plan-hint {
        max-width: none;
    }
}

@media (max-width: 600px) {
    .account-filter,
    .plan-editor__field {
        flex: 1 1 100%;
        min-width: 0;
    }

    .plan-editor {
        flex-wrap: wrap;
    }
}
</style>
