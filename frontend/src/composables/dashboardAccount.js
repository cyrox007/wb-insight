import { ref } from 'vue'
import ProfileServices from '@/API/Dashboard/ProfileServices.js'

const STORAGE_KEY = 'wb-dashboard-token-id'
const accounts = ref([])
const allWbAccounts = ref([])
const selectedTokenId = ref(
    typeof window !== 'undefined' ? (window.localStorage.getItem(STORAGE_KEY) || '') : ''
)
const dashboardVersion = ref(0)
const accountsLoaded = ref(false)
const accountsLoading = ref(false)
const accountsError = ref('')
let loaded = false
let loadingPromise = null
let stateGeneration = 0

const persistSelectedTokenId = (value) => {
    selectedTokenId.value = value || ''
    if (typeof window === 'undefined') return

    if (selectedTokenId.value) {
        window.localStorage.setItem(STORAGE_KEY, selectedTokenId.value)
    } else {
        window.localStorage.removeItem(STORAGE_KEY)
    }
}

const connectionStatus = (token) => {
    if (token.connection_status) return token.connection_status
    if (token.is_revoked) return 'revoked'
    if (token.expires_at && new Date(token.expires_at) < new Date()) return 'expired'
    if (token.is_active === false || token.is_valid === false) return 'inactive'
    if (token.dashboard_available === false) return 'outside_tariff'
    return 'active'
}

export function resetDashboardAccountState() {
    stateGeneration += 1
    accounts.value = []
    allWbAccounts.value = []
    accountsLoaded.value = false
    accountsLoading.value = false
    accountsError.value = ''
    loaded = false
    loadingPromise = null
    persistSelectedTokenId('')
    dashboardVersion.value += 1
}

export function useDashboardAccount() {
    const setSelectedTokenId = (value) => {
        persistSelectedTokenId(value)
    }

    const refreshDashboard = () => {
        dashboardVersion.value += 1
    }

    const loadAccounts = async ({ force = false } = {}) => {
        if (loaded && !force) return accounts.value
        if (loadingPromise && !force) return loadingPromise

        if (loadingPromise && force) {
            stateGeneration += 1
            loadingPromise = null
        }

        const requestGeneration = stateGeneration
        accountsLoading.value = true
        accountsError.value = ''

        const requestPromise = ProfileServices.getProfile()
            .then((response) => {
                if (requestGeneration !== stateGeneration) return accounts.value

                const payload = response?.data || {}
                const tokens = payload.tokens || payload.data?.tokens || []
                allWbAccounts.value = tokens.filter(
                    (token) => token.marketplace === 'wildberries'
                )
                accounts.value = allWbAccounts.value.filter(
                    (token) => connectionStatus(token) === 'active'
                )

                if (
                    selectedTokenId.value &&
                    !accounts.value.some((token) => token.id === selectedTokenId.value)
                ) {
                    setSelectedTokenId('')
                }

                loaded = true
                accountsLoaded.value = true
                return accounts.value
            })
            .catch((error) => {
                if (requestGeneration !== stateGeneration) return accounts.value

                console.error('Не удалось загрузить список кабинетов Wildberries:', error)
                accounts.value = []
                allWbAccounts.value = []
                accountsLoaded.value = true
                accountsError.value =
                    error.response?.data?.error?.message ||
                    'Не удалось проверить доступные кабинеты Wildberries.'
                return accounts.value
            })
            .finally(() => {
                if (requestGeneration !== stateGeneration) return
                accountsLoading.value = false
                if (loadingPromise === requestPromise) {
                    loadingPromise = null
                }
            })

        loadingPromise = requestPromise
        return requestPromise
    }

    const withAccount = (params = {}) => {
        const result = { ...params }
        if (selectedTokenId.value) result.token_id = selectedTokenId.value
        return result
    }

    return {
        accounts,
        allWbAccounts,
        accountsLoaded,
        accountsLoading,
        accountsError,
        selectedTokenId,
        dashboardVersion,
        loadAccounts,
        resetDashboardAccountState,
        setSelectedTokenId,
        refreshDashboard,
        withAccount,
    }
}
