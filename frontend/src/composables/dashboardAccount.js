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

    const refreshDashboard = () => {
        dashboardVersion.value += 1
    }

    const loadAccounts = async ({ force = false } = {}) => {
        if (loaded && !force) return accounts.value
        if (loadingPromise) return loadingPromise

        accountsLoading.value = true
        accountsError.value = ''

        loadingPromise = ProfileServices.getProfile()
            .then((response) => {
                const payload = response?.data || {}
                const tokens = payload.tokens || payload.data?.tokens || []
                allWbAccounts.value = tokens.filter(
                    (token) => token.marketplace === 'wildberries'
                )
                accounts.value = allWbAccounts.value.filter(
                    (token) =>
                        token.is_valid &&
                        token.dashboard_available !== false
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
                accountsLoading.value = false
                loadingPromise = null
            })

        return loadingPromise
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
        setSelectedTokenId,
        refreshDashboard,
        withAccount,
    }
}
