<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import AuthService from '@/API/AuthService'
import BaseButton from '@/components/UI/Buttons/BaseButton.vue'
import TextInput from '@/components/UI/TextInput.vue'

const router = useRouter()
const token = ref('')
const email = ref('')
const password = ref('')
const passwordConfirm = ref('')
const loading = ref(false)
const error = ref('')
const message = ref('')
const requestSent = ref(false)
const resetComplete = ref(false)

const mode = computed(() => token.value ? 'confirm' : 'request')

onMounted(() => {
  const fragment = String(window.location.hash || '').replace(/^#/, '')
  token.value = String(new URLSearchParams(fragment).get('token') || '').trim()
  if (token.value) {
    // Keep the one-time secret out of the visible URL/browser history once it has
    // reached the app. The token remains only in component memory until submit.
    history.replaceState(null, '', `${window.location.pathname}${window.location.search}`)
  }
})

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
    requestSent.value = true
    message.value = response.data?.message || 'Если активный аккаунт с таким email существует, письмо отправлено.'
  } catch (err) {
    error.value = err.response?.data?.error?.message || 'Восстановление доступа временно недоступно'
  } finally {
    loading.value = false
  }
}

async function confirmReset() {
  error.value = ''
  message.value = ''
  if (!token.value) {
    error.value = 'Ссылка восстановления не содержит одноразовый код.'
    return
  }
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
    resetComplete.value = true
    message.value = response.data?.message || 'Пароль изменён. Войдите с новым паролем.'
    password.value = ''
    passwordConfirm.value = ''
    token.value = ''
  } catch (err) {
    error.value = err.response?.data?.error?.message || 'Ссылка восстановления недействительна или истекла'
  } finally {
    loading.value = false
  }
}

async function openLogin() {
  await router.push('/')
  window.dispatchEvent(new CustomEvent('wb:open-login'))
}
</script>

<template>
  <main class="recovery-shell">
    <section class="recovery-card" aria-live="polite">
      <div class="recovery-heading">
        <p class="recovery-eyebrow">WB Insight · безопасность аккаунта</p>
        <h1>{{ mode === 'confirm' && !resetComplete ? 'Установите новый пароль' : resetComplete ? 'Пароль изменён' : 'Восстановление доступа' }}</h1>
        <p v-if="mode === 'request' && !requestSent" class="recovery-description">
          Укажите email аккаунта. В целях безопасности ответ одинаков для существующих и несуществующих адресов.
        </p>
        <p v-else-if="mode === 'confirm' && !resetComplete" class="recovery-description">
          После смены пароля все ранее выданные сессии аккаунта будут отозваны.
        </p>
      </div>

      <form v-if="mode === 'request' && !requestSent" class="recovery-form" @submit.prevent="requestReset">
        <TextInput v-model="email" label="Email" type="email" placeholder="you@example.com" :disabled="loading" />
        <BaseButton type="submit" variant="primary" text="Получить ссылку" loading-text="Отправляем…" :loading="loading" />
      </form>

      <form v-else-if="mode === 'confirm' && !resetComplete" class="recovery-form" @submit.prevent="confirmReset">
        <TextInput v-model="password" label="Новый пароль" type="password" placeholder="Минимум 8 символов" :disabled="loading" />
        <TextInput v-model="passwordConfirm" label="Повторите пароль" type="password" placeholder="Повторите новый пароль" :disabled="loading" />
        <BaseButton type="submit" variant="primary" text="Установить пароль" loading-text="Сохраняем…" :loading="loading" />
      </form>

      <div v-if="message" class="recovery-message recovery-message--success">{{ message }}</div>
      <div v-if="error" class="recovery-message recovery-message--error">{{ error }}</div>

      <div class="recovery-actions">
        <BaseButton
          v-if="requestSent"
          variant="outline"
          text="Отправить ещё раз"
          :disabled="loading"
          @click="requestSent = false; message = ''"
        />
        <BaseButton
          v-if="resetComplete"
          variant="primary"
          text="Войти с новым паролем"
          @click="openLogin"
        />
        <BaseButton
          v-else
          variant="outline"
          text="Вернуться на главную"
          :disabled="loading"
          @click="router.push('/')"
        />
      </div>

      <p v-if="requestSent" class="recovery-hint">
        Проверьте также папки «Спам» и «Промоакции». Повторный запрос в течение короткого интервала не создаёт новое письмо.
      </p>
    </section>
  </main>
</template>

<style scoped>
.recovery-shell {
  min-height: calc(100vh - 64px);
  display: grid;
  place-items: center;
  padding: 28px 16px;
  background:
    radial-gradient(circle at 18% 10%, color-mix(in srgb, var(--secondary-color) 10%, transparent), transparent 26rem),
    var(--dark-bg);
}

.recovery-card {
  width: min(100%, 500px);
  padding: clamp(20px, 4vw, 30px);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  background: var(--card-bg);
  box-shadow: var(--shadow);
}

.recovery-heading {
  display: grid;
  gap: 8px;
}

.recovery-eyebrow {
  margin: 0;
  color: var(--secondary-color);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: .08em;
  text-transform: uppercase;
}

h1 {
  margin: 0;
  color: var(--text-color);
  font-size: clamp(25px, 5vw, 34px);
  letter-spacing: -.035em;
}

.recovery-description,
.recovery-hint {
  margin: 0;
  color: var(--text-muted);
  font-size: 13px;
  line-height: 1.55;
}

.recovery-form {
  display: grid;
  gap: 14px;
  margin-top: 22px;
}

.recovery-message {
  margin-top: 16px;
  padding: 12px 14px;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  font-size: 12px;
  line-height: 1.5;
}

.recovery-message--success {
  border-color: color-mix(in srgb, var(--success-color) 35%, var(--border-color));
  background: color-mix(in srgb, var(--success-color) 8%, var(--card-bg));
  color: var(--text-color);
}

.recovery-message--error {
  border-color: color-mix(in srgb, var(--danger-color) 35%, var(--border-color));
  background: color-mix(in srgb, var(--danger-color) 8%, var(--card-bg));
  color: var(--danger-color);
}

.recovery-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 9px;
  margin-top: 18px;
}

.recovery-hint {
  margin-top: 14px;
}

@media (max-width: 520px) {
  .recovery-shell {
    align-items: start;
    padding: 14px 10px 24px;
  }

  .recovery-card {
    border-radius: 14px;
  }

  .recovery-actions {
    display: grid;
  }
}
</style>
