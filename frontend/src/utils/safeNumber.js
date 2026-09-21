export function toFiniteNumber(value, fallback = null) {
  if (value === null || value === undefined || value === '') return fallback
  const numeric = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(numeric) ? numeric : fallback
}

export function formatFiniteNumber(
  value,
  {
    locale = 'ru-RU',
    minimumFractionDigits,
    maximumFractionDigits = 2,
    fallback = '—',
  } = {},
) {
  const numeric = toFiniteNumber(value)
  if (numeric === null) return fallback

  const options = { maximumFractionDigits }
  if (minimumFractionDigits !== undefined) {
    options.minimumFractionDigits = minimumFractionDigits
  }

  return new Intl.NumberFormat(locale, options).format(numeric)
}

export function finiteOrZero(value) {
  return toFiniteNumber(value, 0)
}
