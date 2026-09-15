<template>
    <div class="account-tools">
        <label class="account-filter">
            <span class="account-filter__label">Кабинет WB</span>
            <select class="account-filter__select" :value="selectedTokenId" @change="onChange">
                <option value="">Все кабинеты</option>
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
            <label class="plan-editor__field">
                <span class="account-filter__label">План месяца, ₽</span>
                <input
                    v-model="planTarget"
                    class="plan-editor__input"
                    type="number"
                    min="0.01"
                    step="0.01"
                    placeholder="Например, 500000"
                    :disabled="isSaving"
                />
            </label>
            <button class="plan-editor__button" type="submit" :disabled="isSaving || !planTarget">
                Сохранить
            </button>
            <button class="plan-editor__reset" type="button" :disabled="isSaving" @click="removePlan">
                Сбросить
            </button>
        </form>

        <div v-else-if="route.name === 'dashboard.home'" class="plan-editor__hint">
            Выберите конкретный кабинет, чтобы задать месячный план.
        </div>
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

onMounted(async () => {
    await loadAccounts()
})
</script>

<style scoped>
.account-tools {
    display: flex;
    align-items: flex-end;
    gap: 12px;
    flex-wrap: wrap;
}

.account-filter,
.plan-editor__field {
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

.account-filter__select,
.plan-editor__input {
    min-height: 38px;
    padding: 8px 10px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background: var(--light-bg);
    color: var(--text-color);
    font: inherit;
}

.account-filter__select:focus,
.plan-editor__input:focus {
    outline: none;
    border-color: var(--secondary-color);
}

.plan-editor {
    display: flex;
    align-items: flex-end;
    gap: 8px;
}

.plan-editor__field {
    min-width: 175px;
}

.plan-editor__button,
.plan-editor__reset {
    min-height: 38px;
    padding: 8px 12px;
    border-radius: 6px;
    border: 1px solid var(--border-color);
    cursor: pointer;
    font: inherit;
}

.plan-editor__button {
    background: var(--secondary-color);
    color: white;
    border-color: var(--secondary-color);
}

.plan-editor__reset {
    background: transparent;
    color: var(--text-color);
}

.plan-editor__button:disabled,
.plan-editor__reset:disabled {
    opacity: 0.55;
    cursor: default;
}

.plan-editor__hint {
    max-width: 240px;
    font-size: 12px;
    line-height: 1.35;
    color: var(--text-color);
    opacity: 0.65;
}

@media (max-width: 760px) {
    .account-tools,
    .plan-editor {
        width: 100%;
    }

    .account-filter,
    .plan-editor__field {
        flex: 1 1 100%;
    }

    .plan-editor {
        flex-wrap: wrap;
    }
}
</style>
