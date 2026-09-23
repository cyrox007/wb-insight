<script setup>
import { computed, onMounted, ref } from 'vue'
import ProfileServices from '@/API/Dashboard/ProfileServices.js'
import SellerInputsService from '@/API/Dashboard/SellerInputsService.js'

const props = defineProps({
  syncStatus: {
    type: Object,
    default: null,
  },
  isSyncing: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['refresh'])

const profile = ref(null)
const costTotal = ref(0)
const costStatusKnown = ref(false)
const isLoading = ref(true)
const dismissed = ref(false)

const connectionStatus = (token) => {
  if (token.connection_status) return token.connection_status
  if (token.is_revoked) return 'revoked'
  if (token.expires_at && new Date(token.expires_at) < new Date()) return 'expired'
  if (token.is_active === false || token.is_valid === false) return 'inactive'
  if (token.dashboard_available === false) return 'outside_tariff'
  return 'active'
}

const activeConnections = computed(() =>
  (profile.value?.tokens || []).filter(
    token => token.marketplace === 'wildberries' && connectionStatus(token) === 'active'
  )
)

const hasConnection = computed(() => activeConnections.value.length > 0)
const readyEntities = computed(() => Number(props.syncStatus?.ready_entities || 0))
const staleEntities = computed(() => Number(props.syncStatus?.stale_entities || 0))
const totalEntities = computed(() => Number(props.syncStatus?.total_entities || 0))
const hasUsefulData = computed(() => readyEntities.value + staleEntities.value > 0)
const syncComplete = computed(() => props.syncStatus?.complete === true)
const hasCosts = computed(() => costStatusKnown.value && costTotal.value > 0)

const onboardingProgress = computed(() => {
  let completed = 0
  if (hasConnection.value) completed += 1
  if (hasUsefulData.value) completed += 1
  if (hasCosts.value) completed += 1
  return completed
})

const syncProgressText = computed(() => {
  if (!hasConnection.value) return 'Сначала подключите кабинет.'
  if (!props.syncStatus) return props.isSyncing ? 'Wildberries подключён. Проверяем первые данные…' : 'Ожидаем запуск синхронизации.'
  if (syncComplete.value) return 'Все источники первичной аналитики готовы.'
  return `Готово источников: ${readyEntities.value} из ${totalEntities.value || 10}.`
})

const entityTone = (status) => {
  if (status === 'ready') return 'ready'
  if (status === 'error') return 'error'
  if (status === 'stale') return 'warning'
  return 'waiting'
}

const dismissKey = computed(() =>
  profile.value?.user?.id ? `wb-onboarding-dismissed-${profile.value.user.id}` : ''
)

const visible = computed(() => !dismissed.value)

async function loadContext() {
  isLoading.value = true
  try {
    const response = await ProfileServices.getProfile()
    profile.value = response.data || {}

    if (dismissKey.value && localStorage.getItem(dismissKey.value) === '1') {
      dismissed.value = true
    }

    if (!hasConnection.value) {
      costTotal.value = 0
      costStatusKnown.value = true
      return
    }

    try {
      const costs = await SellerInputsService.getCostProducts({ limit: 1, offset: 0 })
      costTotal.value = Number(costs.data?.data?.total || 0)
      costStatusKnown.value = true
    } catch {
      costStatusKnown.value = false
    }
  } finally {
    isLoading.value = false
  }
}

function dismiss() {
  if (dismissKey.value) localStorage.setItem(dismissKey.value, '1')
  dismissed.value = true
}

async function refresh() {
  emit('refresh')
  await loadContext()
}

onMounted(loadContext)
</script>

<template>
  <section v-if="visible" class="onboarding-card" aria-label="Первый запуск WB Insight">
    <div class="onboarding-head">
      <div>
        <p class="onboarding-eyebrow">Первый запуск</p>
        <h2>До первых полезных цифр — три шага</h2>
        <p>
          WB Insight сам загрузит данные Wildberries. От вас нужны подключение кабинета
          и, для точной прибыли, себестоимость.
        </p>
      </div>
      <div class="onboarding-progress" :aria-label="`Выполнено шагов: ${onboardingProgress} из 3`">
        <strong>{{ onboardingProgress }}/3</strong>
        <span>выполнено</span>
      </div>
    </div>

    <div v-if="isLoading" class="onboarding-loading" role="status">
      Проверяем готовность кабинета…
    </div>

    <div v-else class="onboarding-steps">
      <article class="onboarding-step" :class="{ 'is-done': hasConnection }">
        <span class="step-number">{{ hasConnection ? '✓' : '1' }}</span>
        <div>
          <strong>{{ hasConnection ? 'Wildberries подключён' : 'Подключите Wildberries' }}</strong>
          <p v-if="hasConnection">
            {{ activeConnections.length === 1 ? 'Кабинет готов к загрузке данных.' : `Подключено кабинетов: ${activeConnections.length}.` }}
          </p>
          <p v-else>Покажем точные права и проверим токен автоматически.</p>
        </div>
        <RouterLink
          v-if="!hasConnection"
          class="step-action"
          :to="{ path: '/dashboard/profile', query: { tab: 'connections' } }"
        >
          Подключить
        </RouterLink>
      </article>

      <article class="onboarding-step" :class="{ 'is-done': hasUsefulData }">
        <span class="step-number">{{ hasUsefulData ? '✓' : '2' }}</span>
        <div>
          <strong>{{ hasUsefulData ? 'Первые данные готовы' : 'Дождитесь загрузки данных' }}</strong>
          <p>{{ syncProgressText }}</p>
        </div>
        <button v-if="hasConnection && !syncComplete" type="button" class="step-action" @click="refresh">
          Проверить
        </button>
      </article>

      <article class="onboarding-step" :class="{ 'is-done': hasCosts }">
        <span class="step-number">{{ hasCosts ? '✓' : '3' }}</span>
        <div>
          <strong>{{ hasCosts ? 'Себестоимость добавлена' : 'Добавьте себестоимость' }}</strong>
          <p>
            {{ hasCosts
              ? `Заполнено товаров: ${costTotal}.`
              : 'Не блокирует старт. Нужна для корректной прибыли и юнит-экономики.' }}
          </p>
        </div>
        <RouterLink
          v-if="!hasCosts"
          class="step-action step-action--secondary"
          :to="{ path: '/dashboard/profile', query: { tab: 'costs' } }"
        >
          Заполнить
        </RouterLink>
      </article>
    </div>

    <div v-if="hasConnection && props.syncStatus?.entities?.length" class="sync-sources">
      <span
        v-for="entity in props.syncStatus.entities"
        :key="entity.entity"
        class="sync-source"
        :class="`sync-source--${entityTone(entity.status)}`"
      >
        <i aria-hidden="true"></i>
        {{ entity.label }}
      </span>
    </div>

    <div class="onboarding-footer">
      <p v-if="hasUsefulData && !hasCosts">
        Продажи и выплаты уже можно смотреть. Прибыль станет точнее после добавления себестоимости.
      </p>
      <p v-else-if="hasUsefulData">
        Основная настройка завершена. Дополнительные расходы и месячный план можно добавить позже.
      </p>
      <p v-else>
        Не нужно ждать всю синхронизацию: аналитика начнёт открываться по мере появления данных.
      </p>
      <button v-if="hasUsefulData" type="button" class="dismiss-button" @click="dismiss">
        Скрыть подсказки
      </button>
    </div>
  </section>
</template>

<style scoped>
.onboarding-card {
  margin-bottom: 18px;
  padding: 18px;
  border: 1px solid color-mix(in srgb, var(--secondary-color) 22%, var(--border-color));
  border-radius: var(--radius-lg);
  background:
    linear-gradient(135deg, color-mix(in srgb, var(--secondary-color) 8%, var(--card-bg)), var(--card-bg) 48%);
  box-shadow: var(--shadow-sm);
}

.onboarding-head {
  display: flex;
  justify-content: space-between;
  gap: 18px;
}

.onboarding-head h2 {
  margin-top: 3px;
  color: var(--text-color);
  font-size: 20px;
  letter-spacing: -0.02em;
}

.onboarding-head p {
  max-width: 720px;
  margin-top: 6px;
  color: var(--text-muted);
  font-size: 13px;
  line-height: 1.55;
}

.onboarding-eyebrow {
  color: var(--secondary-color) !important;
  font-size: 10px !important;
  font-weight: 800;
  letter-spacing: .08em;
  text-transform: uppercase;
}

.onboarding-progress {
  min-width: 92px;
  padding: 9px 12px;
  align-self: flex-start;
  display: grid;
  justify-items: end;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  background: var(--card-bg);
}

.onboarding-progress strong {
  color: var(--text-color);
  font-size: 18px;
}

.onboarding-progress span {
  color: var(--text-subtle);
  font-size: 10px;
}

.onboarding-loading {
  margin-top: 14px;
  padding: 14px;
  border-radius: 10px;
  background: var(--light-bg);
  color: var(--text-muted);
  font-size: 13px;
}

.onboarding-steps {
  margin-top: 14px;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.onboarding-step {
  min-width: 0;
  padding: 13px;
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 9px;
  align-items: start;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  background: var(--card-bg);
}

.onboarding-step.is-done {
  border-color: color-mix(in srgb, #22a06b 28%, var(--border-color));
}

.step-number {
  width: 25px;
  height: 25px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: color-mix(in srgb, var(--secondary-color) 12%, var(--card-bg));
  color: var(--secondary-color);
  font-size: 11px;
  font-weight: 800;
}

.is-done .step-number {
  background: color-mix(in srgb, #22a06b 12%, var(--card-bg));
  color: #16815a;
}

.onboarding-step strong {
  color: var(--text-color);
  font-size: 13px;
}

.onboarding-step p {
  margin-top: 4px;
  color: var(--text-muted);
  font-size: 11px;
  line-height: 1.45;
}

.step-action {
  grid-column: 2;
  width: fit-content;
  min-height: 30px;
  margin-top: 2px;
  padding: 5px 9px;
  display: inline-flex;
  align-items: center;
  border: 1px solid var(--secondary-color);
  border-radius: 8px;
  background: var(--secondary-color);
  color: #fff;
  font-size: 11px;
  font-weight: 750;
  cursor: pointer;
}

.step-action--secondary {
  background: transparent;
  color: var(--secondary-color);
}

.sync-sources {
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.sync-source {
  padding: 4px 7px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border: 1px solid var(--border-color);
  border-radius: 999px;
  background: var(--card-bg);
  color: var(--text-muted);
  font-size: 10px;
}

.sync-source i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-subtle);
}

.sync-source--ready i { background: #22a06b; }
.sync-source--warning i { background: #d49a2b; }
.sync-source--error i { background: var(--danger-color); }

.onboarding-footer {
  margin-top: 12px;
  padding-top: 10px;
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  border-top: 1px solid var(--border-color);
}

.onboarding-footer p {
  color: var(--text-muted);
  font-size: 11px;
}

.dismiss-button {
  flex: 0 0 auto;
  border: 0;
  background: transparent;
  color: var(--text-subtle);
  font-size: 11px;
  cursor: pointer;
}

.dismiss-button:hover {
  color: var(--text-color);
}

@media (max-width: 860px) {
  .onboarding-steps {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .onboarding-card {
    padding: 14px;
  }

  .onboarding-head,
  .onboarding-footer {
    align-items: stretch;
    flex-direction: column;
  }

  .onboarding-progress {
    justify-items: start;
  }
}
</style>
