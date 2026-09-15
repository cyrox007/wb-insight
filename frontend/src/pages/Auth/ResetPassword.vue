<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AuthService from '@/API/AuthService'

const route = useRoute()
const router = useRouter()
const token = computed(() => {
  const fragment = String(route.hash || '').replace(/^#/, '')
  return String(new URLSearchParams(fragment).get('token') || '').trim()
})
const email = ref('')
const password = ref('')
const passwordConfirm = ref('')
const loading = ref(false)
const error = ref('')
const message = ref('')

async function requestReset() {
  error.value = ''
  message.value = ''
  if (!email.value.trim()) {
    error.value = 'Укажите email'
    return
  }
  loading.value = true
  try {
    const response = await AuthService.requestPasswordReset(email.value.trim())
    message.value = response.data?.message || 'Если аккаунт существует, письмо отправлено.'
  } catch (err) {
    error.value = err.response?.data?.error?.message || 'Не удалось отправить письмо восстановления'
  } finally {
    loading.value = false
  }
}

async function confirmReset() {
  error.value = ''
  message.value = ''
  if (password.value.length < 8) {
    error.value = 'Пароль должен содержать минимум 8 символов'
    return
  }
  if (password.value !== passwordConfirm.value) {
    error.value = 'Пароли не совпадают'
    return
  }
  loading.value = true
  try {
    const response = await AuthService.confirmPasswordReset(token.value, password.value)
    message.value = response.data?.message || 'Пароль изменён'
    password.value = ''
    passwordConfirm.value = ''
  } catch (err) {
    error.value = err.response?.data?.error?.message || 'Ссылка восстановления недействительна'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="recovery-page">
    <section class="recovery-card">
      <p class="eyebrow">WB Insight</p>
      <h1>{{ token ? 'Новый пароль' : 'Восстановление доступа' }}</h1>
      <p class="description" v-if="!token">
        Укажите email аккаунта. Ответ одинаков для существующих и несуществующих адресов.
      </p>
      <p class="description" v-else>
        После смены пароля все ранее выданные сессии будут отозваны.
      </p>

      <form v-if="!token" @submit.prevent="requestReset">
        <label>
          <span>Email</span>
          <input v-model="email" type="email" autocomplete="email" required />
        </label>
        <button type="submit" :disabled="loading">{{ loading ? 'Отправляем…' : 'Получить ссылку' }}</button>
      </form>

      <form v-else @submit.prevent="confirmReset">
        <label>
          <span>Новый пароль</span>
          <input v-model="password" type="password" autocomplete="new-password" minlength="8" required />
        </label>
        <label>
          <span>Повторите пароль</span>
          <input v-model="passwordConfirm" type="password" autocomplete="new-password" minlength="8" required />
        </label>
        <button type="submit" :disabled="loading">{{ loading ? 'Сохраняем…' : 'Установить пароль' }}</button>
      </form>

      <p v-if="message" class="message success">{{ message }}</p>
      <p v-if="error" class="message error">{{ error }}</p>
      <button class="back" type="button" @click="router.push('/')">Вернуться на главную</button>
    </section>
  </main>
</template>

<style scoped>
.recovery-page { min-height: 100vh; display: grid; place-items: center; padding: 24px; background: var(--bg, #111318); }
.recovery-card { width: min(100%, 460px); padding: 28px; border: 1px solid rgba(255,255,255,.1); border-radius: 18px; background: rgba(255,255,255,.04); }
.eyebrow { opacity: .65; margin: 0 0 8px; }
h1 { margin: 0 0 10px; }
.description { opacity: .75; line-height: 1.5; }
form { display: grid; gap: 14px; margin-top: 22px; }
label { display: grid; gap: 7px; }
input { width: 100%; box-sizing: border-box; padding: 12px 14px; border-radius: 10px; border: 1px solid rgba(255,255,255,.14); background: rgba(0,0,0,.18); color: inherit; }
button { padding: 12px 16px; border: 0; border-radius: 10px; cursor: pointer; font-weight: 600; }
form button { background: #e5484d; color: white; }
button:disabled { opacity: .6; cursor: wait; }
.message { margin-top: 16px; line-height: 1.45; }
.success { color: #86d993; }
.error { color: #ff8b8b; }
.back { margin-top: 14px; background: transparent; color: inherit; border: 1px solid rgba(255,255,255,.14); }
</style>
