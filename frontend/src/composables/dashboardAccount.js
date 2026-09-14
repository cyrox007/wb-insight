import { ref } from 'vue'
import ProfileServices from '@/API/Dashboard/ProfileServices.js'

const STORAGE_KEY = 'wb-dashboard-token-id'
const accounts = ref([])
const selectedTokenId = ref(
    typeof window !== 'undefined' ? (window.localStorage.getItem(STORAGE_KEY) || '') : ''
)
let loaded = false
let loadingPromise = null

export function useDashboardAccount() {
    const loadAccounts = async () => {
        if (loaded) return accounts.value
        if (loadingPromise) return loadingPromise

        loadingPromise = ProfileServices.getProfile()
            .then((response) => {
                const payload = response?.data || {}
                const tokens = payload.tokens || payload.data?.tokens || []
                accounts.value = tokens.filter(
                    (token) => token.marketplace === 'wildberries' && token.is_valid
                )

                if (
                    selectedTokenId.value &&
                    !accounts.value.some((token) => token.id === selectedTokenId.value)
                ) {
                    setSelectedTokenId('')
                }
                loaded = true
                return accounts.value
            })
            .finally(() => {
                loadingPromise = null
            })

        return loadingPromise
    }

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

    const withAccount = (params = {}) => {
        const result = { ...params }
        if (selectedTokenId.value) result.token_id = selectedTokenId.value
        return result
    }

    return {
        accounts,
        selectedTokenId,
        loadAccounts,
        setSelectedTokenId,
        withAccount,
    }
}
