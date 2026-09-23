<template>
  <Modal :is-open="isOpen" @close="close">
    <template #header>
      <div class="modal-header">
        <div>
          <p class="eyebrow">Подключение за несколько минут</p>
          <h3>Добавить кабинет Wildberries</h3>
        </div>
      </div>
    </template>

    <template #body>
      <details class="token-guide" open>
        <summary>Как создать правильный токен</summary>
        <ol>
          <li>
            Откройте кабинет продавца Wildberries и перейдите:
            <b>Профиль организации → Интеграции по API</b>.
          </li>
          <li>
            Нажмите <b>Создать токен → Для интеграции вручную → Базовый токен</b>.
          </li>
          <li>
            Включите только необходимые категории:
            <div class="permission-chips" aria-label="Необходимые категории WB API">
              <span>Контент</span>
              <span>Аналитика</span>
              <span>Цены и скидки</span>
              <span>Статистика</span>
              <span>Продвижение</span>
              <span>Финансы</span>
            </div>
          </li>
          <li>
            Выберите уровень доступа <b>Только чтение</b>, создайте токен и вставьте его ниже.
          </li>
        </ol>

        <div class="guide-actions">
          <a href="https://seller.wildberries.ru/" target="_blank" rel="noopener noreferrer">
            Открыть кабинет Wildberries
          </a>
          <span>Персональный и тестовый токены для облачного WB Insight не подходят.</span>
        </div>
      </details>

      <TextInput v-model="label" label="Название кабинета" placeholder="Например: Основной магазин" />

      <TextareaInput
        v-model="token"
        type="textarea"
        label="WB API токен"
        placeholder="Вставьте токен продавца..."
        :error="errorMessage"
        :disabled="loading"
        :rows="5"
      />

      <div v-if="errorMessage" class="diagnostic" role="alert">
        <strong>Что нужно сделать</strong>
        <p>{{ errorHint || 'Проверьте параметры токена по инструкции выше и повторите подключение.' }}</p>
        <small v-if="errorCode">Код проверки: {{ errorCode }}</small>
      </div>

      <div class="automatic-check">
        <strong>WB Insight проверит всё автоматически</strong>
        <span>тип токена</span>
        <span>срок действия</span>
        <span>категории</span>
        <span>режим «Только чтение»</span>
        <span>доступность токена в WB API</span>
      </div>

      <LegalConsentChecklist
        v-model="legalConsents"
        context="marketplace_credential"
        @valid="legalValid = $event"
      />
    </template>

    <template #footer>
      <ButtonCancel @click="close" :disabled="loading" />
      <ButtonSuccess
        text="Проверить и подключить"
        :loading="loading"
        :disabled="!legalValid || loading"
        @click="submit"
      />
    </template>
  </Modal>
</template>

<script setup>
import { ref } from 'vue'
import { notify } from '@/composables/notification'

import Modal from '@/components/UI/Modal.vue'
import TextInput from '@/components/UI/TextInput.vue'
import TextareaInput from '@/components/UI/TextareaInput.vue'
import ButtonSuccess from '@/components/UI/Buttons/ButtonSuccess.vue'
import ButtonCancel from '@/components/UI/Buttons/ButtonCancel.vue'
import LegalConsentChecklist from '@/components/LegalConsentChecklist.vue'

import ProfileServices from '@/API/Dashboard/ProfileServices'

defineProps({
  isOpen: Boolean,
})

const emit = defineEmits(['close', 'success'])

const token = ref('')
const label = ref('')
const loading = ref(false)
const errorMessage = ref('')
const errorCode = ref('')
const errorHint = ref('')
const legalConsents = ref([])
const legalValid = ref(false)

const diagnosticHints = {
  WB_TOKEN_PERMISSIONS_MISSING:
    'Создайте новый базовый токен и включите категории, которые перечислены в сообщении проверки.',
  WB_TOKEN_MUST_BE_READ_ONLY:
    'Создайте новый токен с уровнем доступа «Только чтение». Права на изменение данных WB Insight не нужны.',
  WB_PERSONAL_TOKEN_NOT_ALLOWED:
    'Вернитесь в «Интеграции по API» и создайте отдельный базовый токен для WB Insight.',
  WB_TEST_TOKEN_NOT_SUPPORTED:
    'Создайте обычный базовый токен в рабочем кабинете продавца Wildberries.',
  WB_TOKEN_EXPIRED:
    'Срок действия этого токена закончился. Создайте новый токен и повторите подключение.',
  WB_TOKEN_REJECTED:
    'Проверьте, что токен не отозван и активен в кабинете Wildberries. При сомнении создайте новый.',
  WB_SERVICE_TOKEN_MISMATCH:
    'Этот сервисный токен выпущен для другой интеграции. Создайте токен именно для WB Insight.',
  WB_SERVICE_CREDENTIALS_NOT_CONFIGURED:
    'Это проблема настройки WB Insight, а не вашего кабинета. Передайте сообщение администратору сервиса.',
  WB_PARTNER_AUTH_REJECTED:
    'Wildberries отклонил связку сервиса и токена. Ваши настройки менять не нужно — требуется проверка интеграции WB Insight.',
  WB_TOKEN_VALIDATION_UNAVAILABLE:
    'Wildberries временно недоступен для проверки. Сохраните токен у себя и повторите попытку позже.',
  WB_TOKEN_VALIDATION_RATE_LIMITED:
    'Wildberries временно ограничил проверки токенов. Повторите подключение позже.',
}

function clearError() {
  errorMessage.value = ''
  errorCode.value = ''
  errorHint.value = ''
}

function applyError(error, fallback) {
  errorMessage.value = error?.message || fallback
  errorCode.value = error?.code || ''
  errorHint.value = diagnosticHints[errorCode.value] || ''
}

const close = () => {
  if (loading.value) return
  clearError()
  token.value = ''
  label.value = ''
  legalConsents.value = []
  legalValid.value = false
  emit('close')
}

const validate = () => {
  if (!token.value || token.value.trim().length === 0) {
    return 'Введите токен'
  }

  if (token.value.trim().length < 20) {
    return 'Токен слишком короткий'
  }

  if (!legalValid.value) {
    return 'Примите актуальные условия подключения кабинета'
  }

  return ''
}

const submit = async () => {
  clearError()

  const validationError = validate()
  if (validationError) {
    errorMessage.value = validationError
    return
  }

  loading.value = true
  try {
    const response = await ProfileServices.add_user_token({
      token: token.value.trim(),
      label: label.value.trim(),
      legal_consents: legalConsents.value,
    })

    const result = response.data || {}
    if (result.status === 'error') {
      applyError(result.error, 'Не удалось проверить токен Wildberries')
      notify.error(errorMessage.value)
      return
    }

    notify.success(
      result.message || 'Кабинет Wildberries подключён. Первичная синхронизация поставлена в очередь.'
    )
    emit('success', result.data)
  } catch (requestError) {
    applyError(
      requestError?.response?.data?.error,
      'Не удалось связаться с сервером. Проверьте соединение и повторите попытку.'
    )
    notify.error(errorMessage.value)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.modal-header h3 {
  margin-top: 2px;
}

.eyebrow {
  color: var(--secondary-color);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: .08em;
  text-transform: uppercase;
}

.token-guide {
  margin-bottom: 14px;
  padding: 12px;
  border: 1px solid color-mix(in srgb, var(--secondary-color) 20%, var(--border-color));
  border-radius: 11px;
  background: color-mix(in srgb, var(--secondary-color) 6%, var(--card-bg));
}

.token-guide summary {
  color: var(--text-color);
  font-size: 13px;
  font-weight: 750;
  cursor: pointer;
}

.token-guide ol {
  margin: 10px 0 0 20px;
  padding: 0;
}

.token-guide li {
  margin-bottom: 8px;
  color: var(--text-muted);
  font-size: 12px;
  line-height: 1.5;
}

.permission-chips {
  margin-top: 6px;
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}

.permission-chips span {
  padding: 3px 6px;
  border: 1px solid var(--border-color);
  border-radius: 999px;
  background: var(--card-bg);
  color: var(--text-color);
  font-size: 10px;
  font-weight: 650;
}

.guide-actions {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.guide-actions a {
  flex: 0 0 auto;
  color: var(--secondary-color);
  font-size: 11px;
  font-weight: 750;
}

.guide-actions span {
  color: var(--text-subtle);
  font-size: 10px;
}

.diagnostic {
  margin: 10px 0;
  padding: 10px 12px;
  border: 1px solid color-mix(in srgb, var(--danger-color) 28%, var(--border-color));
  border-radius: 9px;
  background: color-mix(in srgb, var(--danger-color) 7%, var(--card-bg));
}

.diagnostic strong {
  color: var(--text-color);
  font-size: 12px;
}

.diagnostic p {
  margin-top: 4px;
  color: var(--text-muted);
  font-size: 11px;
  line-height: 1.45;
}

.diagnostic small {
  display: block;
  margin-top: 5px;
  color: var(--text-subtle);
  font-size: 9px;
}

.automatic-check {
  margin: 10px 0 14px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 5px;
}

.automatic-check strong {
  width: 100%;
  margin-bottom: 2px;
  color: var(--text-color);
  font-size: 11px;
}

.automatic-check span {
  padding: 3px 6px;
  border-radius: 999px;
  background: var(--light-bg);
  color: var(--text-muted);
  font-size: 9px;
}

@media (max-width: 560px) {
  .guide-actions {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
