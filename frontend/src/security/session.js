let accessToken = null

export const getAccessToken = () => accessToken

export const setAccessToken = (token) => {
  accessToken = typeof token === 'string' && token.length > 0 ? token : null
}

export const clearAccessToken = () => {
  accessToken = null
}

export const purgeLegacyPersistentAuth = () => {
  // Начиная с P28 токены доступа не хранятся в постоянном хранилище браузера.
  // При первом запуске после обновления удаляем значения от старых сборок.
  localStorage.removeItem('access_token')
  localStorage.removeItem('user')
  sessionStorage.removeItem('access_token')
  sessionStorage.removeItem('user')
}
