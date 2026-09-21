<script setup>
defineProps({
  kind: {
    type: String,
    default: 'empty',
    validator: (value) => ['loading', 'account', 'empty', 'error'].includes(value),
  },
  title: {
    type: String,
    default: '',
  },
  message: {
    type: String,
    default: '',
  },
  actionLabel: {
    type: String,
    default: '',
  },
  actionTo: {
    type: [String, Object],
    default: '',
  },
})

defineEmits(['retry'])
</script>

<template>
  <section class="dashboard-state" :class="`dashboard-state--${kind}`" :aria-live="kind === 'error' ? 'assertive' : 'polite'">
    <template v-if="kind === 'loading'">
      <div class="dashboard-skeleton__header">
        <span></span>
        <span></span>
      </div>
      <div class="dashboard-skeleton__grid">
        <span v-for="index in 5" :key="index" class="dashboard-skeleton__card"></span>
      </div>
      <div class="dashboard-skeleton__panels">
        <span></span>
        <span></span>
      </div>
    </template>

    <template v-else>
      <div class="dashboard-state__icon" aria-hidden="true">
        <svg v-if="kind === 'account'" viewBox="0 0 24 24">
          <path d="M4 7.5h16v11H4zM7 4.5h10v3H7zM8 11h8M8 14.5h5" />
        </svg>
        <svg v-else-if="kind === 'error'" viewBox="0 0 24 24">
          <path d="M12 3 2.8 19h18.4L12 3Z" /><path d="M12 9v4M12 16.5h.01" />
        </svg>
        <svg v-else viewBox="0 0 24 24">
          <path d="M4 6h16v12H4zM8 10h8M8 14h5" />
        </svg>
      </div>
      <div class="dashboard-state__copy">
        <h2>{{ title || (kind === 'account' ? 'Нет доступного кабинета Wildberries' : kind === 'error' ? 'Не удалось загрузить данные' : 'Данных пока нет') }}</h2>
        <p v-if="message">{{ message }}</p>
      </div>
      <div v-if="actionLabel" class="dashboard-state__actions">
        <RouterLink v-if="actionTo" :to="actionTo" class="dashboard-state__button">
          {{ actionLabel }}
        </RouterLink>
        <button v-else type="button" class="dashboard-state__button" @click="$emit('retry')">
          {{ actionLabel }}
        </button>
      </div>
    </template>
  </section>
</template>

<style scoped>
.dashboard-state {
  width: min(100% - 32px, var(--content-width));
  margin: 24px auto 44px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  background: var(--card-bg);
  box-shadow: var(--shadow-sm);
}

.dashboard-state:not(.dashboard-state--loading) {
  min-height: 260px;
  padding: 40px 28px;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 16px;
  text-align: center;
}

.dashboard-state--error {
  border-color: color-mix(in srgb, var(--danger-color) 30%, var(--border-color));
}

.dashboard-state__icon {
  width: 52px;
  height: 52px;
  display: grid;
  place-items: center;
  border-radius: 16px;
  color: var(--secondary-color);
  background: color-mix(in srgb, var(--secondary-color) 11%, var(--card-bg));
}

.dashboard-state--error .dashboard-state__icon {
  color: var(--danger-color);
  background: color-mix(in srgb, var(--danger-color) 10%, var(--card-bg));
}

.dashboard-state__icon svg {
  width: 26px;
  height: 26px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.7;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.dashboard-state__copy h2 {
  color: var(--text-color);
  font-size: 20px;
  letter-spacing: -0.02em;
}

.dashboard-state__copy p {
  max-width: 620px;
  margin-top: 7px;
  color: var(--text-muted);
  font-size: 14px;
  line-height: 1.6;
}

.dashboard-state__button {
  min-height: 40px;
  padding: 9px 15px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--secondary-color);
  border-radius: 9px;
  background: var(--secondary-color);
  color: #fff;
  font-weight: 700;
  cursor: pointer;
  transition: background 220ms ease, transform 220ms ease;
}

.dashboard-state__button:hover {
  background: var(--secondary-hover);
  transform: translateY(-1px);
}

.dashboard-state--loading {
  padding: 24px;
  overflow: hidden;
}

.dashboard-skeleton__header,
.dashboard-skeleton__grid,
.dashboard-skeleton__panels {
  display: grid;
  gap: 12px;
}

.dashboard-skeleton__header {
  grid-template-columns: minmax(180px, 360px) 180px;
  justify-content: space-between;
}

.dashboard-skeleton__header span,
.dashboard-skeleton__card,
.dashboard-skeleton__panels span {
  position: relative;
  overflow: hidden;
  border-radius: 10px;
  background: var(--light-bg);
}

.dashboard-skeleton__header span {
  height: 42px;
}

.dashboard-skeleton__grid {
  margin-top: 20px;
  grid-template-columns: repeat(5, minmax(0, 1fr));
}

.dashboard-skeleton__card {
  height: 108px;
}

.dashboard-skeleton__panels {
  margin-top: 14px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.dashboard-skeleton__panels span {
  height: 220px;
}

.dashboard-skeleton__header span::after,
.dashboard-skeleton__card::after,
.dashboard-skeleton__panels span::after {
  content: '';
  position: absolute;
  inset: 0;
  transform: translateX(-100%);
  background: linear-gradient(90deg, transparent, color-mix(in srgb, var(--text-color) 7%, transparent), transparent);
  animation: dashboard-shimmer 1.45s ease-in-out infinite;
}

@keyframes dashboard-shimmer {
  to { transform: translateX(100%); }
}

:global(.dashboard-page) > .dashboard-state {
  width: 100%;
  margin-inline: 0;
}

@media (max-width: 900px) {
  .dashboard-skeleton__grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .dashboard-skeleton__panels {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .dashboard-state {
    width: min(100% - 20px, var(--content-width));
  }

  .dashboard-state--loading {
    padding: 16px;
  }

  .dashboard-skeleton__header {
    grid-template-columns: 1fr;
  }

  .dashboard-skeleton__grid {
    grid-template-columns: 1fr;
  }
}

@media (prefers-reduced-motion: reduce) {
  .dashboard-skeleton__header span::after,
  .dashboard-skeleton__card::after,
  .dashboard-skeleton__panels span::after {
    animation: none;
  }
}
</style>
