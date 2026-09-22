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

        <div
            v-if="accounts.length"
            class="sync-summary"
            :class="`sync-summary--${syncTone}`"
            role="status"
            :title="syncDetails"
        >
            <span class="sync-summary__dot" aria-hidden="true"></span>
            <span>{{ syncSummaryText }}</span>
            <button
                class="sync-summary__refresh"
                type="button"
                :disabled="syncStatusLoading"
                aria-label="Обновить статус синхронизации"
                title="Обновить статус синхронизации"
                @click="loadSyncStatus"
            >
                ↻
            </button>
        </div>
    </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import DashboardService from '@/API/Dashboard/DashboardService.js'
import { notify } from '@/composables/notification'
import { useDashboardAccount } from '@/composables/dashboardAccount.js'

const emit = defineEmits(['change'])
const route = useRoute()
const planTarget = ref('')
const isSaving = ref(false)
const syncStatus = ref(null)
const syncStatusLoading = ref(false)
const syncStatusError = ref('')
let syncStatusTimer = null

const {
    accounts,
    accountsLoading,
    selectedTokenId,
    loadAccounts,
    setSelectedTokenId,
    refreshDashboard,
} = useDashboardAccount()

const formatSyncTime = (value) => {
    if (!value) return ''
    const parsed = new Date(value)
    if (Number.isNaN(parsed.getTime())) return ''
    return new Intl.DateTimeFormat('ru-RU', {
        day: '2-digit',
        month: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
    }).format(parsed)
}

const syncTone = computed(() => {
    if (syncStatusError.value) return 'error'
    if (syncStatusLoading.value && !syncStatus.value) return 'loading'
    if (!syncStatus.value) return 'neutral'
    if (syncStatus.value.is_syncing) return 'syncing'
    if (syncStatus.value.complete) return 'ready'
    if (Number(syncStatus.value.error_entities || 0) > 0) return 'error'
    return 'warning'
})

const syncSummaryText = computed(() => {
    if (syncStatusLoading.value && !syncStatus.value) return 'Проверяем свежесть данных…'
    if (syncStatusError.value) return syncStatusError.value
    if (!syncStatus.value) return 'Статус синхронизации недоступен'

    const ready = Number(syncStatus.value.ready_entities || 0)
    const total = Number(syncStatus.value.total_entities || 0)
    const oldest = formatSyncTime(syncStatus.value.oldest_success_at)

    if (syncStatus.value.is_syncing) {
        return `Обновляем данные · готово ${ready}/${total}`
    }
    if (syncStatus.value.complete) {
        return oldest ? `Актуально · не старше ${oldest}` : 'Данные актуальны'
    }

    const errorCount = Number(syncStatus.value.error_entities || 0)
    const waitingCount = Number(syncStatus.value.waiting_entities || 0)
    const staleCount = Number(syncStatus.value.stale_entities || 0)
    const details = []
    if (errorCount) details.push(`ошибки: ${errorCount}`)
    if (waitingCount) details.push(`ожидают: ${waitingCount}`)
    if (staleCount) details.push(`устарели: ${staleCount}`)
    return `Актуально ${ready}/${total}${details.length ? ` · ${details.join(' · ')}` : ''}`
})

const syncDetails = computed(() => {
    if (!syncStatus.value?.entities?.length) return syncSummaryText.value
    const labels = {
        ready: 'актуально',
        stale: 'устарело',
        error: 'ошибка',
        waiting: 'ожидает синхронизации',
    }
    return syncStatus.value.entities
        .map((item) => `${item.label}: ${labels[item.status] || item.status}`)
        .join('\n')
})

const loadSyncStatus = async () => {
    if (!accounts.value.length || syncStatusLoading.value) return

    syncStatusLoading.value = true
    syncStatusError.value = ''
    try {
        const params = selectedTokenId.value
            ? { token_id: selectedTokenId.value }
            : {}
        const response = await DashboardService.get_sync_status(params)
        const result = response.data || {}
        if (result.status === 'error') {
            syncStatus.value = null
            syncStatusError.value =
                result.error?.message || 'Не удалось проверить свежесть данных'
            return
        }
        syncStatus.value = result.sync_status || null
    } catch (error) {
        syncStatusError.value =
            error.response?.data?.error?.message ||
            'Не удалось проверить свежесть данных'
    } finally {
        syncStatusLoading.value = false
    }
}

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

watch(
    () => [selectedTokenId.value, accounts.value.length],
    () => {
        if (accounts.value.length) loadSyncStatus()
    }
)

onMounted(async () => {
    await loadAccounts()
    await loadSyncStatus()
    syncStatusTimer = window.setInterval(loadSyncStatus, 60000)
})

onBeforeUnmount(() => {
    if (syncStatusTimer !== null) {
        window.clearInterval(syncStatusTimer)
    }
})
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

.sync-summary {
    grid-column: 1 / -1;
    justify-self: end;
    min-height: 24px;
    max-width: 100%;
    padding: 4px 7px 4px 8px;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    border: 1px solid var(--border-color);
    border-radius: 999px;
    background: var(--card-bg);
    color: var(--text-muted);
    font-size: 10px;
    line-height: 1.25;
}

.sync-summary__dot {
    width: 6px;
    height: 6px;
    flex: 0 0 auto;
    border-radius: 50%;
    background: var(--text-subtle);
}

.sync-summary--ready .sync-summary__dot {
    background: #22a06b;
}

.sync-summary--syncing .sync-summary__dot,
.sync-summary--loading .sync-summary__dot {
    background: #4f86da;
}

.sync-summary--warning .sync-summary__dot {
    background: #d49a2b;
}

.sync-summary--error .sync-summary__dot {
    background: var(--danger-color);
}

.sync-summary__refresh {
    width: 19px;
    height: 19px;
    display: grid;
    place-items: center;
    border: 0;
    border-radius: 6px;
    background: transparent;
    color: var(--text-subtle);
    cursor: pointer;
}

.sync-summary__refresh:hover:not(:disabled) {
    background: var(--hover-bg);
    color: var(--text-color);
}

.sync-summary__refresh:disabled {
    opacity: 0.45;
    cursor: default;
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

    .sync-summary {
        justify-self: stretch;
        width: 100%;
        border-radius: 8px;
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

    .sync-summary {
        align-items: flex-start;
    }
}
</style>
