<template>
    <Modal :is-open="isOpen" @close="$emit('close')">
        <template #header>
            <div class="modal-header">
                <h3 class="modal-title">Регистрация</h3>
                <button class="modal-close" @click="$emit('close')">&times;</button>
            </div>
        </template>

        <template #body></template>

        <template #footer>
            <div class="modal-footer">
                <button class="btn btn-outline" @click="$emit('close')">Отмена</button>
                <button class="btn btn-primary" @click="performLogin" :disabled="modalLoadedBtn">
                    <SpinnerButtonSmall v-if="modalLoadedBtn" />
                    <span>Войти</span>
                </button>
            </div>
        </template>
    </Modal>
</template>

<script setup>
import Modal from '@/components/UI/Modal.vue'
</script>

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
</style>