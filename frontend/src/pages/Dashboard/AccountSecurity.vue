<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import AccountLifecycleService from '@/API/AccountLifecycleService'
import AuthService from '@/API/AuthService'
import { notify } from '@/composables/notification'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()
const reason = ref('')
const confirmText = ref('')
const loading = ref(false)

async function deactivate() {
  if (confirmText.value !== 'ДЕАКТИВИРОВАТЬ') {
    notify.error('Введите ДЕАКТИВИРОВАТЬ для подтверждения')
    return
  }
  if (!confirm('Деактивировать аккаунт? Подключения WB будут отозваны, а текущие сессии перестанут работать.')) return

  loading.value = true
  try {
    const response = await AccountLifecycleService.deactivateAccount(reason.value.trim() || null)
    try { await AuthService.logout() } catch (_) {}
    authStore.logout()
    localStorage.removeItem('access_token')
    localStorage.removeItem('user')
    localStorage.removeItem('redirectPath')
    localStorage.removeItem('wb-dashboard-token-id')
    notify.success(response.data?.message || 'Аккаунт деактивирован')
    await router.push('/')
  } catch (error) {
    notify.error(error.response?.data?.error?.message || 'Не удалось деактивировать аккаунт')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <section class="security-page">
    <header>
      <p class="eyebrow">Безопасность аккаунта</p>
      <h1>Доступ и деактивация</h1>
      <p>Смена забытого пароля выполняется через подтверждённый email. Деактивация не удаляет финансовые, legal и audit-данные немедленно.</p>
    </header>

    <article class="card">
      <h2>Восстановление доступа</h2>
      <p>Если требуется сменить пароль через email, используйте отдельный recovery flow. После успешной смены все ранее выданные сессии становятся недействительными.</p>
      <button class="secondary" type="button" @click="router.push('/reset-password')">Перейти к восстановлению</button>
    </article>

    <article class="card danger-zone">
      <p class="eyebrow danger">Опасная зона</p>
      <h2>Деактивировать аккаунт</h2>
      <p>Доступ прекратится сразу. Сессии будут отозваны, marketplace credentials отключены, автопродление активной подписки — остановлено. Данные сохраняются на срок retention и не стираются этой кнопкой.</p>
      <label>
        <span>Причина, необязательно</span>
        <textarea v-model="reason" maxlength="1000" rows="3" placeholder="Можно указать причину для support/audit" />
      </label>
      <label>
        <span>Для подтверждения введите ДЕАКТИВИРОВАТЬ</span>
        <input v-model="confirmText" autocomplete="off" />
      </label>
      <button class="danger-button" type="button" :disabled="loading || confirmText !== 'ДЕАКТИВИРОВАТЬ'" @click="deactivate">
        {{ loading ? 'Деактивируем…' : 'Деактивировать аккаунт' }}
      </button>
    </article>
  </section>
</template>

<style scoped>
.security-page { width: min(100% - 32px, 840px); margin: 0 auto; padding: 28px 0 64px; display: grid; gap: 16px; }
header { margin-bottom: 4px; }
h1 { margin: 4px 0 10px; font-size: clamp(28px, 4vw, 38px); }
header > p:last-child, .card p { color: var(--text-muted); line-height: 1.55; }
.eyebrow { color: #a78bfa; font-size: 11px; font-weight: 750; letter-spacing: .08em; text-transform: uppercase; }
.eyebrow.danger { color: #fda4af; }
.card { padding: 22px; border: 1px solid var(--border-color); border-radius: var(--radius-lg); background: var(--card-bg); }
.card h2 { margin: 0 0 8px; }
.danger-zone { border-color: rgba(251,113,133,.28); }
label { display: grid; gap: 7px; margin-top: 14px; }
label span { color: var(--text-muted); font-size: 12px; }
input, textarea { box-sizing: border-box; width: 100%; padding: 11px 12px; border: 1px solid var(--border-color); border-radius: 9px; background: var(--light-bg); color: var(--text-color); resize: vertical; }
button { margin-top: 16px; min-height: 38px; padding: 8px 14px; border-radius: 9px; cursor: pointer; font-weight: 650; }
.secondary { border: 1px solid var(--border-color); background: transparent; color: var(--text-color); }
.danger-button { border: 1px solid rgba(251,113,133,.45); background: rgba(190,24,93,.18); color: #fecdd3; }
button:disabled { opacity: .5; cursor: default; }
</style>
