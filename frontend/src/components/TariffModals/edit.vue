<script setup>
import { ref, onMounted, watch } from 'vue';
import CP_Tariffs from '@/API/ControlPanel/CP_Tariffs';
import Modal from '@/components/UI/Modal.vue';
import TextInput from '@/components/UI/TextInput.vue';
import ButtonCancel from '@/components/UI/Buttons/ButtonCancel.vue';
import ButtonPrimary from '@/components/UI/Buttons/ButtonPrimary.vue';

const props = defineProps({
	isOpen: Boolean,
	currentTariff: Object
});

const emit = defineEmits(['close', 'updated']);
const tariffData = ref({
	name: '',
	description: '',
	price_rub: '',
	is_active: false,
	is_public: false
})
const modalLoadedBtn = ref(false);

watch(
	() => props.currentTariff,
	(newTariff) => {
		if (newTariff && newTariff.id) {
			tariffData.value = {
				name: newTariff.name || '',
				description: newTariff.description || '',
				price_rub: String(newTariff.price_rub ?? ''),
				is_active: Boolean(newTariff.is_active),
				is_public: Boolean(newTariff.is_public)
			}
		}
	},
	{ immediate: true }
)

const editTariff = async () => {
	modalLoadedBtn.value = true;
	try {
		const payload = {
			name: tariffData.value.name,
			description: tariffData.value.description,
			price_rub: parseFloat(tariffData.value.price_rub) || 0,
			is_active: tariffData.value.is_active,
			is_public: tariffData.value.is_public
		};

		const response = await CP_Tariffs.editTariff(props.currentTariff.id, payload);
		if (response.data.status === 'success') {
			emit('updated');
			setTimeout(() => {
				modalLoadedBtn.value = false;
				emit('close')
			}, 1000);
		}
	} catch (error) {
		console.error('Ошибка редактирования тарифа:', error);
		modalLoadedBtn.value = false;
	}
}
</script>

<template>
	<Modal :is-open="isOpen" @close="$emit('close')">
		<template #header>
			<h3>Редактировать тариф</h3>
		</template>
		<template #body>
			<TextInput label="Название тарифа" v-model="tariffData.name" />
			<TextInput label="Описание тарифа" v-model="tariffData.description" />
			<TextInput v-model="tariffData.price_rub" label="Цена" placeholder="Введите цену тарифа" type="number" />

			<div class="form-group">
				<label class="toggle-label">
					Активен ли тариф?
					<div class="toggle-switch" @click="tariffData.is_active = !tariffData.is_active">
						<div class="toggle-slider" :class="{ 'toggle-on': tariffData.is_active }"></div>
					</div>
				</label>
				<div class="toggle-hint">{{ typeof tariffData.is_active }}
					{{ tariffData.is_active ? 'Тариф доступен для подключения' : 'Тариф неактивен' }}
				</div>
			</div>
			<div class="form-group">
				<label class="toggle-label">
					Опубликован ли тариф?
					<div class="toggle-switch" @click="tariffData.is_public = !tariffData.is_public">
						<div class="toggle-slider" :class="{ 'toggle-on': tariffData.is_public }"></div>
					</div>
				</label>
				<div class="toggle-hint">
					{{ tariffData.is_public ? 'Тариф опубликован' : 'Тариф скрыт' }}
				</div>
			</div>
		</template>
		<template #footer>
			<ButtonCancel @click="$emit('close')" :text="'Отмена'" />
			<ButtonPrimary @click="editTariff" :loading="modalLoadedBtn" :text="'Сохранить'" />
		</template>
	</Modal>
</template>

<style scoped>
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