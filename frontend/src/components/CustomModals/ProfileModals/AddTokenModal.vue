<template>
    <div class="modal-overlay" @click.self="close">
        <div class="modal">
            <div class="modal-header">
                <h3>Добавить токен Wildberries</h3>
                <button class="close-btn" @click="close">✕</button>
            </div>

            <div class="modal-body">
                <TextareaInput v-model="token" label="WB API токен" placeholder="Вставьте токен продавца..."
                    :disabled="loading" :rows="5" />

                <div v-if="errorMessage" class="error-text">
                    {{ errorMessage }}
                </div>

                <p class="hint">
                    Токен используется только для чтения данных (Analytics, Statistics, Promotion)
                </p>
            </div>

            <div class="modal-footer">
                <ButtonCancel @click="close" :disabled="loading" />

                <ButtonSuccess :text="'Добавить токен'" :loading="loading" @click="submit" />
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref } from 'vue'
import { notify } from '@/composables/notification'
import ProfileServices from '@/API/Dashboard/ProfileServices'

// UI
import ButtonSuccess from '@/components/UI/Buttons/ButtonSuccess.vue'
import ButtonCancel from '@/components/UI/Buttons/ButtonCancel.vue'
import TextareaInput from '@/components/UI/TextareaInput.vue'

const emit = defineEmits(['close', 'success'])

const token = ref('')
const loading = ref(false)
const errorMessage = ref(null)

// --- Закрытие ---
const close = () => {
    if (loading.value) return
    emit('close')
}

// --- Валидация ---
const validate = () => {
    if (!token.value || token.value.trim().length === 0) {
        return 'Введите токен'
    }

    if (token.value.length < 20) {
        return 'Токен слишком короткий'
    }

    if (!/^[A-Za-z0-9\.\-_]+$/.test(token.value)) {
        return 'Некорректный формат токена'
    }

    return null
}

// --- Submit ---
const submit = async () => {
    errorMessage.value = null

    const validationError = validate()
    if (validationError) {
        errorMessage.value = validationError
        return
    }

    try {
        loading.value = true

        const response = await ProfileServices.add_user_token({
            token: token.value.trim()
        })

        const result = response.data

        if (result.status === 'error') {
            errorMessage.value = result.error.message || 'Ошибка при добавлении токена'
            notify.error(errorMessage.value)
            return
        }

        notify.success('Токен успешно добавлен')

        emit('success')

    } catch (e) {
        console.error(e)
        errorMessage.value = 'Ошибка соединения с сервером'
        notify.error(errorMessage.value)
    } finally {
        loading.value = false
    }
}
</script>

<style scoped>
.modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
}

.modal {
    width: 100%;
    max-width: 500px;
    background: var(--card-bg);
    border-radius: 12px;
    box-shadow: var(--shadow);
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 16px;
}

.modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.modal-body {
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.modal-footer {
    display: flex;
    justify-content: flex-end;
    gap: 10px;
    margin-top: 10px;
}

.close-btn {
    background: none;
    border: none;
    font-size: 18px;
    cursor: pointer;
}

.error-text {
    color: var(--accent-color);
    font-size: 0.85rem;
}

.hint {
    font-size: 0.85rem;
    color: #888;
}
</style>