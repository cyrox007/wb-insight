<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { isStaffUser, ROLE_LABELS } from '@/security/roles'
import { notify } from '@/composables/notification'
import ProfileServices from '@/API/Dashboard/ProfileServices'
import SellerInputsService from '@/API/Dashboard/SellerInputsService'
import SelectTariffModal from '@/components/CustomModals/ProfileModals/SelectTariffModal.vue'
import AddTokenModal from '@/components/CustomModals/ProfileModals/AddTokenModal.vue'

const authStore = useAuthStore()
const isStaff = computed(() => isStaffUser(authStore.getUser))
const staffRoleLabels = computed(() =>
  (authStore.getUser?.roles || [])
    .filter(role => role !== 'user')
    .map(role => ROLE_LABELS[role] || role)
)
const activeTab = ref('profile')
const isLoading = ref(true)
const isSavingProfile = ref(false)
const addBtnLoading = ref(false)
const showAddTokenModal = ref(false)
const showTariffModal = ref(false)

const user = ref({})
const subscription = ref(null)
const tokens = ref([])

const profileForm = reactive({
  full_name: '',
  entity_type: 'individual',
  tax_percent: 0,
  timezone: 'Europe/Moscow',
})

const costProducts = ref([])
const isCostsLoading = ref(false)
const isCostSaving = ref(false)
const costForm = reactive({
  nm_id: '',
  seller_sku: '',
  product_name: '',
  cost_price: '',
  effective_from: '',
  comment: '',
})
const costFileInput = ref(null)

const expenses = ref([])
const isExpensesLoading = ref(false)
const isExpenseSaving = ref(false)
const expenseFilterTokenId = ref('')
const expensePeriodStart = ref('')
const expensePeriodEnd = ref('')
const editingExpenseId = ref(null)
const expenseForm = reactive({
  token_id: '',
  date: '',
  category: '',
  amount: '',
  nm_id: '',
  description: '',
})

const sellerTabs = [
  { key: 'profile', label: 'Профиль и налог' },
  { key: 'connections', label: 'Кабинеты WB' },
  { key: 'costs', label: 'Себестоимость' },
  { key: 'expenses', label: 'Прочие расходы' },
]

const tabs = computed(() => (
  isStaff.value
    ? [{ key: 'profile', label: 'Профиль' }]
    : sellerTabs
))

const entityTypes = [
  { value: 'individual', label: 'Физическое лицо' },
  { value: 'self_employed', label: 'Самозанятый' },
  { value: 'legal_entity', label: 'Юридическое лицо' },
]

const timezoneOptions = [
  'Europe/Moscow',
  'Europe/Berlin',
  'Europe/Kaliningrad',
  'Asia/Yekaterinburg',
  'Asia/Omsk',
  'Asia/Krasnoyarsk',
  'Asia/Irkutsk',
  'Asia/Yakutsk',
  'Asia/Vladivostok',
  'Asia/Magadan',
  'Asia/Kamchatka',
  'UTC',
]

const availableTokens = computed(() => tokens.value.filter(token =>
  token.marketplace === 'wildberries' &&
  token.dashboard_available !== false &&
  !isTokenExpired(token)
))

const totalExpenses = computed(() => expenses.value.reduce(
  (sum, item) => sum + Number(item.amount || 0),
  0,
))

const money = (value) => {
  const number = Number(value)
  if (!Number.isFinite(number)) return '—'
  return `${new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 }).format(number)} ₽`
}

const dateLabel = (value) => {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return new Intl.DateTimeFormat('ru-RU').format(date)
}

const inputDate = (date) => {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function isTokenExpired(token) {
  if (token.is_revoked || token.is_active === false || token.is_valid === false) return true
  return Boolean(token.expires_at && new Date(token.expires_at) < new Date())
}

function getStatusLabel(status) {
  switch (status) {
    case 'active': return 'Активна'
    case 'demo': return 'Демо'
    case 'expired': return 'Истекла'
    case 'cancelled': return 'Отменена'
    default: return 'Нет подписки'
  }
}

function tokenLabel(tokenId) {
  const token = tokens.value.find(item => item.id === tokenId)
  return token?.label || (tokenId ? `WB · ${String(tokenId).slice(0, 8)}` : '—')
}

function syncProfileForm() {
  profileForm.full_name = user.value.full_name || ''
  profileForm.entity_type = user.value.entity_type || 'individual'
  profileForm.tax_percent = Math.round(Number(user.value.tax_rate || 0) * 10000) / 100
  profileForm.timezone = user.value.timezone || 'Europe/Moscow'
}

function resetCostForm() {
  costForm.nm_id = ''
  costForm.seller_sku = ''
  costForm.product_name = ''
  costForm.cost_price = ''
  costForm.effective_from = inputDate(new Date())
  costForm.comment = ''
}

function resetExpenseForm() {
  editingExpenseId.value = null
  expenseForm.token_id = availableTokens.value[0]?.id || ''
  expenseForm.date = inputDate(new Date())
  expenseForm.category = ''
  expenseForm.amount = ''
  expenseForm.nm_id = ''
  expenseForm.description = ''
}

async function loadProfile() {
  isLoading.value = true
  try {
    const response = await ProfileServices.getProfile()
    const result = response.data
    if (result.status === 'error') throw new Error(result.error?.message || 'Не удалось загрузить настройки')

    tokens.value = result.tokens || []
    subscription.value = result.subscription || null
    user.value = result.user || {}
    syncProfileForm()

    if (!expenseForm.token_id && availableTokens.value.length) {
      expenseForm.token_id = availableTokens.value[0].id
    }
  } catch (error) {
    notify.error(error.response?.data?.error?.message || error.message || 'Ошибка загрузки профиля')
  } finally {
    isLoading.value = false
  }
}

async function saveProfile() {
  const taxPercent = Number(profileForm.tax_percent)
  if (!profileForm.full_name.trim()) {
    notify.error(isStaff.value ? 'Укажите имя' : 'Укажите имя или название компании')
    return
  }
  if (!isStaff.value && (!Number.isFinite(taxPercent) || taxPercent < 0 || taxPercent > 100)) {
    notify.error('Налоговая ставка должна быть от 0 до 100%')
    return
  }

  isSavingProfile.value = true
  try {
    const payload = {
      full_name: profileForm.full_name.trim(),
      timezone: profileForm.timezone,
    }
    if (!isStaff.value) {
      payload.entity_type = profileForm.entity_type
      payload.tax_rate = taxPercent / 100
    }

    const response = await ProfileServices.updateProfile(payload)
    const result = response.data
    if (result.status === 'error') {
      notify.error(result.error?.message || 'Не удалось сохранить настройки')
      return
    }

    user.value = result.user
    const storedUser = JSON.parse(localStorage.getItem('user') || '{}')
    const nextStoredUser = { ...storedUser, ...result.user }
    localStorage.setItem('user', JSON.stringify(nextStoredUser))
    authStore.login(nextStoredUser)
    syncProfileForm()
    notify.success('Настройки сохранены')
  } catch (error) {
    notify.error(error.response?.data?.error?.message || 'Не удалось сохранить настройки')
  } finally {
    isSavingProfile.value = false
  }
}

async function openAddTokenModal() {
  addBtnLoading.value = true
  try {
    const response = await ProfileServices.checkTokenPermission(user.value.id)
    if (response.data.status === 'error') {
      notify.error(response.data.error?.message || 'Достигнут лимит кабинетов')
      return
    }
    showAddTokenModal.value = true
  } catch (error) {
    const status = error.response?.status
    const code = error.response?.data?.error?.code
    const message = error.response?.data?.error?.message || 'Не удалось проверить лимит кабинетов'

    if (status === 403 && (code === 'TOKEN_LIMIT_EXCEEDED' || code === 'TARIFF_LIMIT_EXCEEDED')) {
      notify.info(message)
      showTariffModal.value = true
      return
    }

    notify.error(message)
  } finally {
    addBtnLoading.value = false
  }
}

async function handleTokenAdded() {
  await loadProfile()
  showAddTokenModal.value = false
  notify.success('Кабинет Wildberries подключён')
}

async function deleteToken(id) {
  if (!confirm('Удалить подключение Wildberries? Это действие нельзя отменить.')) return
  try {
    const response = await ProfileServices.delete_user_token(id)
    if (response.data.status === 'error') {
      notify.error(response.data.error?.message || 'Не удалось удалить подключение')
      return
    }
    tokens.value = tokens.value.filter(token => token.id !== id)
    if (expenseForm.token_id === id) resetExpenseForm()
    notify.success('Подключение удалено')
  } catch (error) {
    notify.error(error.response?.data?.error?.message || 'Не удалось удалить подключение')
  }
}

async function loadCosts() {
  isCostsLoading.value = true
  try {
    const end = new Date()
    const start = new Date(end)
    start.setDate(start.getDate() - 89)
    const response = await SellerInputsService.getCostProducts({
      start_date: inputDate(start),
      end_date: inputDate(end),
      limit: 200,
      offset: 0,
    })
    const result = response.data
    if (result.status === 'error') throw new Error(result.error?.message || 'Не удалось загрузить товары')
    costProducts.value = result.data?.items || []
  } catch (error) {
    notify.error(error.response?.data?.error?.message || error.message || 'Не удалось загрузить себестоимость')
  } finally {
    isCostsLoading.value = false
  }
}

function editCost(item) {
  costForm.nm_id = String(item.nm_id || '')
  costForm.seller_sku = item.seller_sku || ''
  costForm.product_name = item.product_name || ''
  costForm.cost_price = item.cost_price || ''
  costForm.effective_from = item.cost_effective_from || inputDate(new Date())
  costForm.comment = ''
  document.querySelector('.cost-form')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

async function saveCost() {
  const nmId = Number(costForm.nm_id)
  const cost = Number(costForm.cost_price)
  if (!Number.isInteger(nmId) || nmId <= 0) {
    notify.error('Укажите корректный nmId Wildberries')
    return
  }
  if (!Number.isFinite(cost) || cost < 0) {
    notify.error('Себестоимость не может быть отрицательной')
    return
  }
  if (!costForm.effective_from) {
    notify.error('Укажите дату, с которой действует себестоимость')
    return
  }

  isCostSaving.value = true
  try {
    const response = await SellerInputsService.saveCostPrices([{
      nm_id: nmId,
      seller_sku: costForm.seller_sku || null,
      product_name: costForm.product_name || null,
      cost_price: cost,
      effective_from: costForm.effective_from,
      comment: costForm.comment || null,
      currency: 'RUB',
    }])
    if (response.data.status === 'error') {
      notify.error(response.data.error?.message || 'Не удалось сохранить себестоимость')
      return
    }
    notify.success('Себестоимость сохранена с указанной даты')
    resetCostForm()
    await loadCosts()
  } catch (error) {
    notify.error(error.response?.data?.error?.message || 'Не удалось сохранить себестоимость')
  } finally {
    isCostSaving.value = false
  }
}

async function deleteCost(item) {
  if (!confirm(`Удалить всю историю себестоимости для nmId ${item.nm_id}?`)) return
  try {
    const response = await SellerInputsService.deleteCostPrice(item.nm_id)
    if (response.data.status === 'error') {
      notify.error(response.data.error?.message || 'Не удалось удалить себестоимость')
      return
    }
    notify.success('История себестоимости удалена')
    await loadCosts()
  } catch (error) {
    notify.error(error.response?.data?.error?.message || 'Не удалось удалить себестоимость')
  }
}

function chooseCostFile() {
  costFileInput.value?.click()
}

async function uploadCosts(event) {
  const file = event.target.files?.[0]
  if (!file) return
  isCostSaving.value = true
  try {
    const response = await SellerInputsService.uploadCostPrices(file)
    if (response.data.status === 'error') {
      notify.error(response.data.error?.message || 'Не удалось загрузить CSV')
      return
    }
    notify.success(`Загружено строк: ${response.data.data?.uploaded_count || 0}`)
    await loadCosts()
  } catch (error) {
    notify.error(error.response?.data?.error?.message || 'Не удалось загрузить CSV')
  } finally {
    isCostSaving.value = false
    event.target.value = ''
  }
}

async function loadExpenses() {
  isExpensesLoading.value = true
  try {
    const params = {
      start_date: expensePeriodStart.value,
      end_date: expensePeriodEnd.value,
    }
    if (expenseFilterTokenId.value) params.token_id = expenseFilterTokenId.value

    const response = await SellerInputsService.getExpenses(params)
    const result = response.data
    if (result.status === 'error') throw new Error(result.error?.message || 'Не удалось загрузить расходы')
    expenses.value = result.data?.items || []
  } catch (error) {
    notify.error(error.response?.data?.error?.message || error.message || 'Не удалось загрузить расходы')
  } finally {
    isExpensesLoading.value = false
  }
}

function editExpense(item) {
  editingExpenseId.value = item.id
  expenseForm.token_id = item.token_id
  expenseForm.date = item.date
  expenseForm.category = item.category
  expenseForm.amount = item.amount
  expenseForm.nm_id = item.nm_id || ''
  expenseForm.description = item.description || ''
  document.querySelector('.expense-form')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

async function saveExpense() {
  const amount = Number(expenseForm.amount)
  if (!expenseForm.token_id) {
    notify.error('Выберите кабинет Wildberries')
    return
  }
  if (!expenseForm.date || !expenseForm.category.trim()) {
    notify.error('Укажите дату и категорию расхода')
    return
  }
  if (!Number.isFinite(amount) || amount <= 0) {
    notify.error('Сумма расхода должна быть больше нуля')
    return
  }

  const nmId = expenseForm.nm_id === '' ? null : Number(expenseForm.nm_id)
  if (nmId !== null && (!Number.isInteger(nmId) || nmId <= 0)) {
    notify.error('nmId должен быть положительным числом')
    return
  }

  const payload = {
    token_id: expenseForm.token_id,
    date: expenseForm.date,
    category: expenseForm.category.trim(),
    amount,
    currency: 'RUB',
    nm_id: nmId,
    description: expenseForm.description.trim() || null,
  }

  isExpenseSaving.value = true
  try {
    const response = editingExpenseId.value
      ? await SellerInputsService.updateExpense(editingExpenseId.value, payload)
      : await SellerInputsService.createExpense(payload)
    if (response.data.status === 'error') {
      notify.error(response.data.error?.message || 'Не удалось сохранить расход')
      return
    }
    notify.success(editingExpenseId.value ? 'Расход обновлён' : 'Расход добавлен')
    resetExpenseForm()
    await loadExpenses()
  } catch (error) {
    notify.error(error.response?.data?.error?.message || 'Не удалось сохранить расход')
  } finally {
    isExpenseSaving.value = false
  }
}

async function deleteExpense(item) {
  if (!confirm(`Удалить расход «${item.category}» на ${money(item.amount)}?`)) return
  try {
    const response = await SellerInputsService.deleteExpense(item.id)
    if (response.data.status === 'error') {
      notify.error(response.data.error?.message || 'Не удалось удалить расход')
      return
    }
    if (editingExpenseId.value === item.id) resetExpenseForm()
    notify.success('Расход удалён')
    await loadExpenses()
  } catch (error) {
    notify.error(error.response?.data?.error?.message || 'Не удалось удалить расход')
  }
}

function toPay(paymentId) {
  location.href = `/billing/success?payment_id=${paymentId}`
}

async function selectTab(key) {
  activeTab.value = key
  if (key === 'costs' && !costProducts.value.length) await loadCosts()
  if (key === 'expenses' && !expenses.value.length) await loadExpenses()
}

onMounted(async () => {
  if (!isStaff.value) {
    const now = new Date()
    const monthStart = new Date(now.getFullYear(), now.getMonth(), 1)
    expensePeriodStart.value = inputDate(monthStart)
    expensePeriodEnd.value = inputDate(now)
    resetCostForm()
    resetExpenseForm()
  }
  await loadProfile()
  if (!isStaff.value) resetExpenseForm()
})
</script>

<template>
  <section class="settings-page">
    <header class="settings-header">
      <div>
        <p class="eyebrow">{{ isStaff ? 'Рабочий аккаунт' : 'Настройки продавца' }}</p>
        <h1>{{ isStaff ? 'Профиль сотрудника' : 'Исходные данные и подключения' }}</h1>
        <p v-if="isStaff">Личные данные рабочего аккаунта отделены от клиентского контура. Кабинеты Wildberries, себестоимость и расходы здесь не показываются.</p>
        <p v-else>WB Insight получает маркетплейс-данные автоматически. Здесь остаются только параметры, которые Wildberries не знает: налог, себестоимость, собственные расходы и подключения.</p>
        <div v-if="isStaff && staffRoleLabels.length" class="staff-role-row">
          <span v-for="role in staffRoleLabels" :key="role" class="staff-role-chip">{{ role }}</span>
        </div>
      </div>
      <div v-if="!isStaff" class="subscription-chip">
        <span>{{ subscription?.tariff_name || 'DEMO' }}</span>
        <strong>{{ getStatusLabel(subscription?.status) }}</strong>
        <button type="button" @click="showTariffModal = true">Тариф</button>
      </div>
    </header>

    <nav class="settings-tabs" aria-label="Разделы настроек">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        type="button"
        :class="{ active: activeTab === tab.key }"
        @click="selectTab(tab.key)"
      >
        {{ tab.label }}
      </button>
    </nav>

    <div v-if="isLoading" class="loading-state">Загружаем настройки…</div>

    <template v-else>
      <section v-if="activeTab === 'profile'" class="settings-card">
        <div class="section-heading">
          <div>
            <p class="eyebrow">{{ isStaff ? 'Аккаунт' : 'Расчётные параметры' }}</p>
            <h2>{{ isStaff ? 'Личные настройки' : 'Профиль продавца' }}</h2>
          </div>
          <span class="section-note">Email и телефон меняются через отдельное подтверждение.</span>
        </div>

        <form class="form-grid" @submit.prevent="saveProfile">
          <label class="field field--wide">
            <span>{{ isStaff ? 'Имя' : 'Имя или название компании' }}</span>
            <input v-model="profileForm.full_name" maxlength="255" autocomplete="name" />
          </label>

          <label v-if="!isStaff" class="field">
            <span>Тип продавца</span>
            <select v-model="profileForm.entity_type">
              <option v-for="item in entityTypes" :key="item.value" :value="item.value">{{ item.label }}</option>
            </select>
          </label>

          <label v-if="!isStaff" class="field">
            <span>Налоговая ставка, %</span>
            <input v-model="profileForm.tax_percent" type="number" min="0" max="100" step="0.01" />
            <small>Используется в юнит-экономике и прибыли.</small>
          </label>

          <label class="field">
            <span>Часовой пояс</span>
            <select v-model="profileForm.timezone">
              <option v-for="timezone in timezoneOptions" :key="timezone" :value="timezone">{{ timezone }}</option>
            </select>
          </label>

          <div class="profile-readonly">
            <span>Email</span>
            <strong>{{ user.email }}</strong>
          </div>
          <div class="profile-readonly">
            <span>Телефон</span>
            <strong>{{ user.phone }}</strong>
          </div>

          <div class="form-actions field--wide">
            <button class="primary-button" type="submit" :disabled="isSavingProfile">
              {{ isSavingProfile ? 'Сохраняем…' : 'Сохранить настройки' }}
            </button>
          </div>
        </form>
      </section>

      <section v-else-if="activeTab === 'connections'" class="settings-card">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Автоматическая синхронизация</p>
            <h2>Кабинеты Wildberries</h2>
          </div>
          <button class="primary-button" type="button" :disabled="addBtnLoading" @click="openAddTokenModal">
            {{ addBtnLoading ? 'Проверяем…' : 'Добавить кабинет' }}
          </button>
        </div>

        <div v-if="!tokens.length" class="empty-state">
          <strong>Нет подключённых кабинетов.</strong>
          <span>Добавьте API-токен Wildberries — дальше выгрузки и обновления выполняет система.</span>
        </div>

        <div v-else class="connection-list">
          <article v-for="token in tokens" :key="token.id" class="connection-row">
            <div class="connection-main">
              <span class="connection-mark">WB</span>
              <div>
                <strong>{{ token.label || 'Wildberries' }}</strong>
                <small>{{ token.id.slice(0, 8) }} · добавлен {{ dateLabel(token.issued_at) }}</small>
              </div>
            </div>
            <div class="connection-status" :class="{ bad: isTokenExpired(token), limited: token.dashboard_available === false }">
              {{ isTokenExpired(token) ? 'Недоступен' : token.dashboard_available === false ? 'Вне лимита тарифа' : 'Активен' }}
            </div>
            <button class="danger-link" type="button" @click="deleteToken(token.id)">Удалить</button>
          </article>
        </div>
      </section>

      <section v-else-if="activeTab === 'costs'" class="settings-stack">
        <article class="settings-card cost-form">
          <div class="section-heading">
            <div>
              <p class="eyebrow">Лист «СС»</p>
              <h2>Себестоимость товара</h2>
              <p class="section-description">Новая цена применяется только с указанной даты. Старые периоды сохраняют прежнюю себестоимость.</p>
            </div>
            <div class="secondary-actions">
              <input ref="costFileInput" class="hidden-input" type="file" accept=".csv,text/csv" @change="uploadCosts" />
              <button class="secondary-button" type="button" :disabled="isCostSaving" @click="chooseCostFile">Загрузить CSV</button>
            </div>
          </div>

          <form class="form-grid" @submit.prevent="saveCost">
            <label class="field">
              <span>nmId Wildberries</span>
              <input v-model="costForm.nm_id" type="number" min="1" placeholder="123456789" />
            </label>
            <label class="field">
              <span>Себестоимость, ₽</span>
              <input v-model="costForm.cost_price" type="number" min="0" step="0.01" placeholder="850" />
            </label>
            <label class="field">
              <span>Действует с</span>
              <input v-model="costForm.effective_from" type="date" />
            </label>
            <label class="field">
              <span>Артикул продавца</span>
              <input v-model="costForm.seller_sku" placeholder="Необязательно" />
            </label>
            <label class="field field--wide">
              <span>Название</span>
              <input v-model="costForm.product_name" placeholder="Необязательно" />
            </label>
            <label class="field field--wide">
              <span>Комментарий</span>
              <input v-model="costForm.comment" placeholder="Например: новая закупочная партия" />
            </label>
            <div class="form-actions field--wide">
              <button class="primary-button" type="submit" :disabled="isCostSaving">{{ isCostSaving ? 'Сохраняем…' : 'Сохранить версию' }}</button>
              <button class="secondary-button" type="button" @click="resetCostForm">Очистить</button>
            </div>
          </form>
          <p class="csv-hint">CSV: <code>nm_id,cost_price,effective_from,seller_sku,product_name,comment</code>. Дата — YYYY-MM-DD.</p>
        </article>

        <article class="settings-card">
          <div class="section-heading">
            <div>
              <p class="eyebrow">Последние товары</p>
              <h2>Текущая себестоимость</h2>
            </div>
            <button class="secondary-button" type="button" :disabled="isCostsLoading" @click="loadCosts">Обновить</button>
          </div>

          <div v-if="isCostsLoading" class="loading-state">Загружаем товары…</div>
          <div v-else-if="!costProducts.length" class="empty-state">
            <strong>Товары пока не найдены.</strong>
            <span>Можно добавить себестоимость вручную по nmId или дождаться финансовой синхронизации.</span>
          </div>
          <div v-else class="table-wrapper">
            <table>
              <thead><tr><th>Товар</th><th>nmId</th><th>Себестоимость</th><th>Действует с</th><th></th></tr></thead>
              <tbody>
                <tr v-for="item in costProducts" :key="item.nm_id">
                  <td><strong>{{ item.product_name || item.seller_sku || 'Без названия' }}</strong><small>{{ item.seller_sku || '' }}</small></td>
                  <td>{{ item.nm_id }}</td>
                  <td>{{ item.has_cost ? money(item.cost_price) : 'Не задана' }}</td>
                  <td>{{ item.has_cost ? dateLabel(item.cost_effective_from) : '—' }}</td>
                  <td class="row-actions">
                    <button type="button" @click="editCost(item)">{{ item.has_cost ? 'Изменить' : 'Задать' }}</button>
                    <button v-if="item.has_cost" class="danger-link" type="button" @click="deleteCost(item)">Удалить</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </article>
      </section>

      <section v-else-if="activeTab === 'expenses'" class="settings-stack">
        <article class="settings-card expense-form">
          <div class="section-heading">
            <div>
              <p class="eyebrow">Лист «Прочие расходы»</p>
              <h2>{{ editingExpenseId ? 'Изменить расход' : 'Добавить расход' }}</h2>
              <p class="section-description">Без nmId расход влияет только на общий P&L. С nmId — на конкретный товар и общий итог.</p>
            </div>
          </div>

          <form class="form-grid" @submit.prevent="saveExpense">
            <label class="field">
              <span>Кабинет WB</span>
              <select v-model="expenseForm.token_id">
                <option value="" disabled>Выберите кабинет</option>
                <option v-for="token in availableTokens" :key="token.id" :value="token.id">{{ token.label || 'Wildberries' }}</option>
              </select>
            </label>
            <label class="field"><span>Дата</span><input v-model="expenseForm.date" type="date" /></label>
            <label class="field"><span>Сумма, ₽</span><input v-model="expenseForm.amount" type="number" min="0.01" step="0.01" placeholder="5000" /></label>
            <label class="field">
              <span>Категория</span>
              <input v-model="expenseForm.category" list="expense-categories" maxlength="100" placeholder="Например, упаковка" />
              <datalist id="expense-categories">
                <option value="Упаковка" /><option value="Фулфилмент" /><option value="Доставка до WB" />
                <option value="Сотрудники" /><option value="Сервисы" /><option value="Прочее" />
              </datalist>
            </label>
            <label class="field"><span>nmId, если расход по товару</span><input v-model="expenseForm.nm_id" type="number" min="1" placeholder="Необязательно" /></label>
            <label class="field field--wide"><span>Комментарий</span><input v-model="expenseForm.description" maxlength="500" placeholder="Что это за расход" /></label>
            <div class="form-actions field--wide">
              <button class="primary-button" type="submit" :disabled="isExpenseSaving">{{ isExpenseSaving ? 'Сохраняем…' : editingExpenseId ? 'Сохранить изменения' : 'Добавить расход' }}</button>
              <button v-if="editingExpenseId" class="secondary-button" type="button" @click="resetExpenseForm">Отменить</button>
            </div>
          </form>
        </article>

        <article class="settings-card">
          <div class="section-heading expense-list-heading">
            <div>
              <p class="eyebrow">Период</p>
              <h2>Учтённые расходы · {{ money(totalExpenses) }}</h2>
            </div>
            <form class="expense-filters" @submit.prevent="loadExpenses">
              <select v-model="expenseFilterTokenId">
                <option value="">Все кабинеты</option>
                <option v-for="token in availableTokens" :key="token.id" :value="token.id">{{ token.label || 'Wildberries' }}</option>
              </select>
              <input v-model="expensePeriodStart" type="date" :max="expensePeriodEnd" />
              <input v-model="expensePeriodEnd" type="date" :min="expensePeriodStart" />
              <button class="secondary-button" type="submit">Показать</button>
            </form>
          </div>

          <div v-if="isExpensesLoading" class="loading-state">Загружаем расходы…</div>
          <div v-else-if="!expenses.length" class="empty-state">
            <strong>В этом периоде расходов нет.</strong>
            <span>Если были собственные расходы вне отчёта WB, добавьте их выше — они попадут в прибыль автоматически.</span>
          </div>
          <div v-else class="table-wrapper">
            <table>
              <thead><tr><th>Дата</th><th>Категория</th><th>Кабинет</th><th>nmId</th><th>Сумма</th><th>Комментарий</th><th></th></tr></thead>
              <tbody>
                <tr v-for="item in expenses" :key="item.id">
                  <td>{{ dateLabel(item.date) }}</td>
                  <td><strong>{{ item.category }}</strong></td>
                  <td>{{ tokenLabel(item.token_id) }}</td>
                  <td>{{ item.nm_id || 'Общий' }}</td>
                  <td>{{ money(item.amount) }}</td>
                  <td class="description-cell">{{ item.description || '—' }}</td>
                  <td class="row-actions">
                    <button type="button" @click="editExpense(item)">Изменить</button>
                    <button class="danger-link" type="button" @click="deleteExpense(item)">Удалить</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </article>
      </section>
    </template>
  </section>

  <SelectTariffModal v-if="!isStaff && showTariffModal" :is-open="true" @close="showTariffModal = false" @payment="toPay" />
  <AddTokenModal v-if="!isStaff && showAddTokenModal" :is-open="true" @close="showAddTokenModal = false" @success="handleTokenAdded" />
</template>

<style scoped>
.settings-page { width: min(100% - 32px, 1180px); margin: 0 auto; padding: 22px 0 56px; }
.settings-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; }
.settings-header h1 { margin-top: 3px; font-size: clamp(26px, 3vw, 36px); line-height: 1.08; letter-spacing: -0.035em; }
.settings-header > div:first-child > p:last-child { max-width: 760px; margin-top: 9px; color: var(--text-muted); font-size: 14px; }
.eyebrow { color: var(--secondary-color); font-size: 11px; font-weight: 750; letter-spacing: .08em; text-transform: uppercase; }
.staff-role-row { display:flex; flex-wrap:wrap; gap:6px; margin-top:12px; }
.staff-role-chip { padding:4px 8px; border:1px solid color-mix(in srgb,var(--secondary-color) 24%,var(--border-color)); border-radius:999px; background:color-mix(in srgb,var(--secondary-color) 8%,var(--card-bg)); color:var(--secondary-color); font-size:10px; font-weight:750; }
.subscription-chip { min-width: 180px; padding: 10px 12px; display: grid; grid-template-columns: 1fr auto; gap: 2px 8px; border: 1px solid var(--border-color); border-radius: var(--radius); background: var(--card-bg); }
.subscription-chip span { color: var(--text-muted); font-size: 11px; }
.subscription-chip strong { font-size: 12px; }
.subscription-chip button { grid-column: 1 / -1; margin-top: 5px; padding: 6px; border: 0; border-radius: 7px; background: var(--hover-bg); color: var(--text-color); cursor: pointer; }
.settings-tabs { margin: 20px 0 12px; padding: 5px; display: flex; gap: 4px; overflow-x: auto; border: 1px solid var(--border-color); border-radius: var(--radius); background: var(--header-bg-soft); }
.settings-tabs button { padding: 9px 13px; border: 0; border-radius: 8px; background: transparent; color: var(--text-muted); white-space: nowrap; font-weight: 650; cursor: pointer; }
.settings-tabs button:hover { color: var(--text-color); background: var(--hover-bg); }
.settings-tabs button.active { color: var(--secondary-color); background: color-mix(in srgb, var(--secondary-color) 11%, transparent); }
.settings-card { padding: 20px; border: 1px solid var(--border-color); border-radius: var(--radius-lg); background: linear-gradient(180deg, var(--card-bg-elevated), var(--card-bg)); box-shadow: var(--shadow-sm); }
.settings-stack { display: flex; flex-direction: column; gap: 12px; }
.section-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 18px; margin-bottom: 18px; }
.section-heading h2 { margin-top: 2px; font-size: 18px; }
.section-note, .section-description { margin-top: 5px; color: var(--text-subtle); font-size: 11px; line-height: 1.4; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 13px; }
.field { display: flex; flex-direction: column; gap: 6px; }
.field--wide { grid-column: 1 / -1; }
.field > span { color: var(--text-muted); font-size: 11px; font-weight: 650; }
.field input, .field select, .expense-filters input, .expense-filters select { min-height: 40px; padding: 8px 10px; border: 1px solid var(--border-color); border-radius: 8px; background: var(--light-bg); color: var(--text-color); }
.field small { color: var(--text-subtle); font-size: 10px; }
.profile-readonly { min-height: 58px; padding: 10px; display: flex; flex-direction: column; gap: 5px; border: 1px solid var(--border-color); border-radius: 8px; background: var(--light-bg); }
.profile-readonly span { color: var(--text-subtle); font-size: 10px; }
.profile-readonly strong { font-size: 12px; font-weight: 600; }
.form-actions, .secondary-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.primary-button, .secondary-button, .row-actions button, .danger-link { min-height: 36px; padding: 7px 11px; border-radius: 8px; font-weight: 650; cursor: pointer; }
.primary-button { border: 1px solid var(--secondary-color); background: var(--secondary-color); color: #fff; }
.secondary-button, .row-actions button { border: 1px solid var(--border-color); background: transparent; color: var(--text-muted); }
.primary-button:disabled, .secondary-button:disabled { opacity: .5; cursor: default; }
.danger-link { border: 0; background: transparent; color: var(--danger-color); }
.connection-list { display: flex; flex-direction: column; }
.connection-row { min-height: 68px; padding: 11px 0; display: grid; grid-template-columns: minmax(0, 1fr) auto auto; align-items: center; gap: 14px; border-bottom: 1px solid rgba(148,163,184,.09); }
.connection-row:last-child { border-bottom: 0; }
.connection-main { display: flex; align-items: center; gap: 11px; min-width: 0; }
.connection-main > div { min-width: 0; display: flex; flex-direction: column; }
.connection-main small { color: var(--text-subtle); font-size: 10px; }
.connection-mark { width: 34px; height: 34px; display: grid; place-items: center; border-radius: 9px; background: color-mix(in srgb, var(--secondary-color) 9%, var(--card-bg)); color: var(--secondary-color); font-size: 11px; font-weight: 800; }
.connection-status { padding: 4px 7px; border-radius: 999px; background: color-mix(in srgb, var(--success-color) 8%, var(--card-bg)); color: var(--success-color); font-size: 10px; font-weight: 700; }
.connection-status.bad { background: color-mix(in srgb, var(--danger-color) 8%, var(--card-bg)); color: var(--danger-color); }
.connection-status.limited { background: color-mix(in srgb, var(--warning-color) 8%, var(--card-bg)); color: var(--warning-color); }
.loading-state, .empty-state { min-height: 110px; padding: 24px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 5px; color: var(--text-muted); text-align: center; }
.empty-state strong { color: var(--text-color); font-size: 13px; }
.empty-state span { max-width: 520px; color: var(--text-subtle); font-size: 11px; }
.hidden-input { display: none; }
.csv-hint { margin-top: 12px; color: var(--text-subtle); font-size: 10px; }
.csv-hint code { color: var(--secondary-color); }
.table-wrapper { width: 100%; overflow-x: auto; }
table { width: 100%; min-width: 760px; border-collapse: collapse; font-size: 12px; }
th, td { padding: 11px 9px; border-bottom: 1px solid rgba(148,163,184,.09); text-align: left; vertical-align: middle; }
th { color: var(--text-subtle); font-size: 10px; text-transform: uppercase; }
td > strong { display: block; }
td > small { display: block; margin-top: 2px; color: var(--text-subtle); font-size: 10px; }
.row-actions { text-align: right; white-space: nowrap; }
.row-actions button { margin-left: 4px; min-height: 30px; padding: 5px 8px; font-size: 10px; }
.expense-list-heading { align-items: flex-end; }
.expense-filters { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; justify-content: flex-end; }
.expense-filters input, .expense-filters select { min-height: 34px; padding: 6px 8px; font-size: 11px; }
.description-cell { max-width: 260px; color: var(--text-muted); white-space: normal; }
@media (max-width: 760px) {
  .settings-page { width: min(100% - 20px, 1180px); padding-top: 16px; }
  .settings-header, .section-heading { flex-direction: column; }
  .subscription-chip { width: 100%; }
  .form-grid { grid-template-columns: 1fr; }
  .field--wide { grid-column: auto; }
  .connection-row { grid-template-columns: 1fr auto; }
  .connection-status { grid-column: 1 / 2; width: fit-content; margin-left: 45px; }
  .expense-list-heading { align-items: stretch; }
  .expense-filters { justify-content: flex-start; }
}
</style>
