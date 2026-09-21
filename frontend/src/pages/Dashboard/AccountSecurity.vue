<script setup>
import { computed, ref } from 'vue'
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
const newEmail = ref('')
const pendingEmail = ref('')
const emailBusy = ref(false)

const currentEmail = computed(() => authStore.user?.email || '')

async function requestEmailChange() {
  const target = newEmail.value.trim().toLowerCase()
  if (!target || !target.includes('@')) {
    notify.error('Введите корректный новый email')
    return
  }
  if (target === currentEmail.value.trim().toLowerCase()) {
    notify.error('Укажите email, отличный от текущего')
    return
  }

  emailBusy.value = true
  try {
    const response = await AccountLifecycleService.requestEmailChange(target)
    pendingEmail.value = response.data?.pending_email || target
    newEmail.value = ''
    notify.success(response.data?.message || 'Письмо подтверждения отправлено')
  } catch (error) {
    notify.error(error.response?.data?.error?.message || 'Не удалось запросить смену email')
  } finally {
    emailBusy.value = false
  }
}

async function cancelEmailChange() {
  if (emailBusy.value) return
  emailBusy.value = true
  try {
    const response = await AccountLifecycleService.cancelEmailChange()
    pendingEmail.value = ''
    notify.success(response.data?.message || 'Смена email отменена')
  } catch (error) {
    notify.error(error.response?.data?.error?.message || 'Не удалось отменить смену email')
  } finally {
    emailBusy.value = false
  }
}

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
      <p>Смена email и восстановление пароля требуют подтверждения через почту. Деактивация не удаляет финансовые, legal и audit-данные немедленно.</p>
    </header>

    <article class="card">
      <p class="eyebrow">Email для входа</p>
      <h2>Сменить email</h2>
      <p>Текущий адрес: <strong>{{ currentEmail || '—' }}</strong>. Новый адрес станет логином только после перехода по одноразовой ссылке. После подтверждения текущие сессии будут отозваны.</p>
      <label>
        <span>Новый email</span>
        <input v-model.trim="newEmail" type="email" autocomplete="email" placeholder="new-email@example.com" @keyup.enter="requestEmailChange" />
      </label>
      <div class="email-actions">
        <button class="secondary" type="button" :disabled="emailBusy || !newEmail" @click="requestEmailChange">
          {{ emailBusy ? 'Отправляем…' : 'Отправить подтверждение' }}
        </button>
        <button v-if="pendingEmail" class="link-button" type="button" :disabled="emailBusy" @click="cancelEmailChange">Отменить запрос</button>
      </div>
      <p v-if="pendingEmail" class="pending-note" role="status">
        Ожидает подтверждения: <strong>{{ pendingEmail }}</strong>. До подтверждения продолжайте входить через {{ currentEmail }}.
      </p>
    </article>

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
.eyebrow { color: #6259d9; font-size: 11px; font-weight: 750; letter-spacing: .08em; text-transform: uppercase; }
.eyebrow.danger { color: #c83b55; }
.card { padding: 22px; border: 1px solid var(--border-color); border-radius: var(--radius-lg); background: var(--card-bg); }
.card h2 { margin: 0 0 8px; }
.danger-zone { border-color: rgba(251,113,133,.28); }
label { display: grid; gap: 7px; margin-top: 14px; }
label span { color: var(--text-muted); font-size: 12px; }
input, textarea { box-sizing: border-box; width: 100%; padding: 11px 12px; border: 1px solid var(--border-color); border-radius: 9px; background: var(--light-bg); color: var(--text-color); resize: vertical; }
button { margin-top: 16px; min-height: 38px; padding: 8px 14px; border-radius: 9px; cursor: pointer; font-weight: 650; }
.secondary { border: 1px solid var(--border-color); background: transparent; color: var(--text-color); }
.link-button { border: 0; background: transparent; color: var(--text-muted); text-decoration: underline; }
.email-actions { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
.pending-note { margin: 14px 0 0; padding: 12px 14px; border: 1px solid var(--border-color); border-radius: 9px; background: var(--light-bg); }
.danger-button { border: 1px solid rgba(251,113,133,.45); background: rgba(190,24,93,.18); color: #b4233f; }
button:disabled { opacity: .5; cursor: default; }
</style>
