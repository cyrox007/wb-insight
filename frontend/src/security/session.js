let accessToken = null

export const getAccessToken = () => accessToken

export const setAccessToken = (token) => {
  accessToken = typeof token === 'string' && token.length > 0 ? token : null
}

export const clearAccessToken = () => {
  accessToken = null
}

export const purgeLegacyPersistentAuth = () => {
  // P28 deliberately keeps access credentials out of persistent browser storage.
  // Remove values left by pre-P28 builds during the first load after upgrade.
  localStorage.removeItem('access_token')
  localStorage.removeItem('user')
  sessionStorage.removeItem('access_token')
  sessionStorage.removeItem('user')
}
