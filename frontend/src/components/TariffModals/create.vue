<script setup>
import { ref } from 'vue';
import Modal from '../UI/Modal.vue';
import TextInput from '../UI/TextInput.vue';
import ButtonCancel from '../UI/Buttons/ButtonCancel.vue';
import ButtonPrimary from '../UI/Buttons/ButtonPrimary.vue';
import StringTransform from '@/utils/string_transform.js';
import CP_Tariffs from '@/API/ControlPanel/CP_Tariffs';

const props = defineProps({
    isOpen: Boolean
});

const emit = defineEmits(['close', 'created'])

const modalLoadedBtn = ref(false)

const tariffCode = ref('');
const tariffName = ref('');
const tariffPrice = ref('');
const tariffDescription = ref('');
const isActive = ref(true);

const formError = ref('')

const createTariff = async () => {
    modalLoadedBtn.value = true;
    formError.value = '';
    try {
        if (!tariffCode.value.trim()) {
            return formError.value = 'Поле "Ключ код" обязательно';
        }

        const codeToSend = StringTransform.containsCyrillic(tariffCode.value)
            ? transliterate(tariffCode.value)
            : tariffCode.value;

        if (!tariffName.value.trim()) {
            return formError.value = 'Поле "Название" обязательно';
        }

        // Проверка цены
        const priceStr = tariffPrice.value.trim();
        if (!priceStr) {
            return formError.value = 'Поле "Цена" обязательно';
        }

        // Преобразуем в число (поддерживаем запятую и точку)
        const priceNum = parseFloat(priceStr.replace(',', '.'));
        if (isNaN(priceNum)) {
            return formError.value = 'Цена должна быть числом';
        }
        if (priceNum < 0) {
            return formError.value = 'Цена не может быть отрицательной';
        }
        if (!isFinite(priceNum)) {
            return formError.value = 'Некорректное значение цены';
        }

        // Опционально: округляем до 2 знаков (как в БД NUMERIC(10,2))
        const priceRounded = Number(priceNum.toFixed(2));

        const response = await CP_Tariffs.createTariff({
            code: codeToSend.trim(),
            name: tariffName.value.trim(),
            price: priceRounded,
            description: tariffDescription.value.trim(),
            isActive: isActive.value
        });

        if (response.data?.status === 'success') {
            formError.value = 'Тариф успешно создан!';
            setTimeout(() => {
                emit('close');
            }, 1000);
        } else if (response.data?.status === 'error') {
            formError.value = response.data.message || 'Ошибка при создании тарифа';
        } else {
            formError.value = 'Неожиданный ответ от сервера';
        }
    } catch {
        console.error('Ошибка создания тарифа:', error);
        formError.value = 'Ошибка подключения к серверу';
    } finally {
        modalLoadedBtn.value = false;
    }
}

</script>

<template>
    <Modal :is-open="isOpen" @close="$emit('close')">
        <template #header>
            <div class="modal-header">
                <h3 class="modal-title">Создать тариф</h3>
                <button class="modal-close" @click="$emit('close')">&times;</button>
            </div>
        </template>

        <template #body>
            <div class="modal-body">
                <TextInput v-model="tariffCode" label="Ключ код" placeholder="Параметр должен быть уникальным"
                    type="text" />
                <TextInput v-model="tariffName" label="Название" placeholder="Введите название тарифа" type="text" />
                <TextInput v-model="tariffPrice" label="Цена" placeholder="Введите цену тарифа" type="number" />
                <TextInput v-model="tariffDescription" label="Описание" placeholder="Введите описание тарифа"
                    type="text" />

                <div class="form-group">
                    <label class="toggle-label">
                        Активен ли тариф?
                        <div class="toggle-switch" @click="isActive = !isActive">
                            <div class="toggle-slider" :class="{ 'toggle-on': isActive }"></div>
                        </div>
                    </label>
                    <div class="toggle-hint">
                        {{ isActive ? 'Тариф доступен для подключения' : 'Тариф скрыт и недоступен' }}
                    </div>
                </div>
            </div>
            <div class="modal-error" v-if="formError !== ''" style="color: red;">{{ formError }}</div>
        </template>

        <template #footer>
            <div class="modal-footer">
                <ButtonCancel @click="$emit('close')" />
                <ButtonPrimary @click="createTariff" text="Создать тариф" :loading="modalLoadedBtn"
                    :disabled="modalLoadedBtn" />
            </div>
        </template>
    </Modal>
</template>

<style scoped>
.modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
}

.modal-title {
    font-size: 20px;
    font-weight: 600;
}

.modal-close {
    background: none;
    border: none;
    font-size: 24px;
    cursor: pointer;
    color: #aaa;
}

.modal-body {
    margin-bottom: 20px;
}

.modal-footer {
    display: flex;
    justify-content: flex-end;
    gap: 10px;
}

.form-group {
    margin-bottom: 20px;
}

.toggle-label {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-weight: 500;
    color: var(--text-color);
    cursor: pointer;
    user-select: none;
}

.toggle-switch {
    position: relative;
    width: 50px;
    height: 26px;
}

.toggle-slider {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background-color: #555;
    border-radius: 13px;
    transition: var(--transition);
    cursor: pointer;
}

.toggle-slider::before {
    content: '';
    position: absolute;
    height: 22px;
    width: 22px;
    left: 2px;
    bottom: 2px;
    background-color: white;
    border-radius: 50%;
    transition: var(--transition);
}

.toggle-slider.toggle-on {
    background-color: var(--success-color);
}

.toggle-slider.toggle-on::before {
    transform: translateX(24px);
}

.toggle-hint {
    font-size: 0.85rem;
    color: #aaa;
    margin-top: 6px;
    text-align: right;
}
</style>