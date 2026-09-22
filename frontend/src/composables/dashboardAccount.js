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
let stateVersion = 0

export function useDashboardAccount() {
    const setSelectedTokenId = (value) => {
        selectedTokenId.value = value || ''
        if (typeof window !== 'undefined') {
            if (selectedTokenId.value) {
                window.localStorage.setItem(STORAGE_KEY, selectedTokenId.value)
            } else {
                window.localStorage.removeItem(STORAGE_KEY)
            }
        }
    }

    const resetAccounts = () => {
        stateVersion += 1
        loaded = false
        loadingPromise = null
        accounts.value = []
        allWbAccounts.value = []
        accountsLoaded.value = false
        accountsLoading.value = false
        accountsError.value = ''
        setSelectedTokenId('')
        dashboardVersion.value += 1
    }

    const refreshDashboard = () => {
        dashboardVersion.value += 1
    }

    const loadAccounts = async ({ force = false } = {}) => {
        if (loaded && !force) return accounts.value
        if (loadingPromise && !force) return loadingPromise

        if (loadingPromise && force) {
            stateVersion += 1
            loadingPromise = null
        }

        const requestVersion = stateVersion
        accountsLoading.value = true
        accountsError.value = ''

        let request = null
        request = ProfileServices.getProfile()
            .then((response) => {
                if (requestVersion !== stateVersion) return accounts.value

                const payload = response?.data || {}
                const tokens = payload.tokens || payload.data?.tokens || []
                allWbAccounts.value = tokens.filter(
                    (token) => token.marketplace === 'wildberries'
                )
                accounts.value = allWbAccounts.value.filter((token) => {
                    const status = token.connection_status || (
                        token.is_revoked
                            ? 'revoked'
                            : token.expires_at && new Date(token.expires_at) < new Date()
                                ? 'expired'
                                : token.is_active === false || token.is_valid === false
                                    ? 'inactive'
                                    : token.dashboard_available === false
                                        ? 'outside_tariff'
                                        : 'active'
                    )
                    return status === 'active'
                })

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
                if (requestVersion !== stateVersion) return accounts.value

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
                if (requestVersion === stateVersion) {
                    accountsLoading.value = false
                }
                if (loadingPromise === request) {
                    loadingPromise = null
                }
            })

        loadingPromise = request
        return request
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
        resetAccounts,
        setSelectedTokenId,
        refreshDashboard,
        withAccount,
    }
}
