<script setup>
import { ref, watch } from 'vue'
import Modal from '@/components/UI/Modal.vue'
import TextInput from '@/components/UI/TextInput.vue'
import BaseButton from '@/components/UI/Buttons/BaseButton.vue'
import FormMessage from '@/components/UI/FormMessage.vue'
import CP_Users from '@/API/ControlPanel/CP_Users'

const props = defineProps({
	isOpen: Boolean,
	currentUser: Object
})

const emit = defineEmits(['close', 'updated'])

const emptyUser = () => ({
	full_name: '',
	email: '',
	phone: '',
	entity_type: 'individual',
	inn: '',
	kpp: '',
	legal_address: '',
	timezone: 'Europe/Moscow',
	tax_rate_percent: '20',
	is_staff: false,
	staff_id: '',
	department: '',
	position: ''
})

const userData = ref(emptyUser())

watch(
	() => props.currentUser,
	(newUser) => {
		if (!newUser) return
		userData.value = {
			full_name: newUser.full_name || '',
			email: newUser.email || '',
			phone: newUser.phone || '',
			entity_type: newUser.entity_type || 'individual',
			inn: newUser.inn || '',
			kpp: newUser.kpp || '',
			legal_address: newUser.legal_address || '',
			timezone: newUser.timezone || 'Europe/Moscow',
			tax_rate_percent: String(Math.round(Number(newUser.tax_rate ?? 0.2) * 10000) / 100),
			is_staff: Boolean(newUser.is_staff),
			staff_id: newUser.staff_id || '',
			department: newUser.department || '',
			position: newUser.position || ''
		}
	},
	{ immediate: true }
)

const isSaving = ref(false)
const formMessage = ref('')
const msgStatus = ref('')

async function saveUser() {
	if (isSaving.value || !props.currentUser?.id) return
	formMessage.value = ''
	msgStatus.value = ''

	const fullName = userData.value.full_name.trim()
	const email = userData.value.email.trim().toLowerCase()
	const phone = userData.value.phone.trim()
	const taxRatePercent = Number(userData.value.tax_rate_percent)

	if (!fullName) {
		formMessage.value = 'Укажите имя или название пользователя.'
		msgStatus.value = 'error'
		return
	}
	if (!email || !email.includes('@')) {
		formMessage.value = 'Укажите корректный email.'
		msgStatus.value = 'error'
		return
	}
	if (!phone) {
		formMessage.value = 'Укажите телефон.'
		msgStatus.value = 'error'
		return
	}
	if (!Number.isFinite(taxRatePercent) || taxRatePercent < 0 || taxRatePercent > 100) {
		formMessage.value = 'Налоговая ставка должна быть от 0 до 100%.'
		msgStatus.value = 'error'
		return
	}

	isSaving.value = true
	try {
		const payload = {
			full_name: fullName,
			email,
			phone,
			entity_type: userData.value.entity_type,
			inn: userData.value.inn.trim() || null,
			kpp: userData.value.kpp.trim() || null,
			legal_address: userData.value.legal_address.trim() || null,
			timezone: userData.value.timezone.trim() || 'Europe/Moscow',
			tax_rate: taxRatePercent / 100,
			is_staff: Boolean(userData.value.is_staff),
			staff_id: userData.value.is_staff ? (userData.value.staff_id.trim() || null) : null,
			department: userData.value.is_staff ? (userData.value.department.trim() || null) : null,
			position: userData.value.is_staff ? (userData.value.position.trim() || null) : null
		}

		const response = await CP_Users.updateUser(props.currentUser.id, payload)
		if (response.data?.status === 'success') {
			emit('updated')
			emit('close')
			return
		}
		throw new Error(response.data?.message || 'Не удалось сохранить пользователя')
	} catch (error) {
		formMessage.value = error.response?.data?.error?.message || error.message || 'Ошибка при сохранении пользователя'
		msgStatus.value = 'error'
	} finally {
		isSaving.value = false
	}
}
</script>

<template>
	<Modal
		:is-open="isOpen"
		size="large"
		aria-label="Редактирование пользователя"
		:close-on-overlay-click="!isSaving"
		:close-on-escape="!isSaving"
		@close="$emit('close')"
	>
		<template #header>
			<div>
				<h3 class="cp-modal-title">Редактировать пользователя</h3>
				<p class="cp-muted">Профиль, контактные данные, налоговые и служебные атрибуты.</p>
			</div>
		</template>

		<template #body>
			<div class="cp-form-grid" :aria-busy="isSaving">
				<TextInput label="ФИО / название" v-model="userData.full_name" placeholder="Введите имя или название" :disabled="isSaving" />
				<TextInput label="Email" v-model="userData.email" type="email" :disabled="isSaving" />
				<TextInput label="Телефон" v-model="userData.phone" :disabled="isSaving" />
				<TextInput label="Часовой пояс" v-model="userData.timezone" placeholder="Europe/Moscow" :disabled="isSaving" />

				<div class="cp-form-row">
					<label class="cp-form-label" for="edit-user-tax-rate">Налоговая ставка, %</label>
					<input
						id="edit-user-tax-rate"
						v-model="userData.tax_rate_percent"
						class="cp-form-input"
						type="number"
						min="0"
						max="100"
						step="0.01"
						:disabled="isSaving"
					/>
				</div>

				<div class="cp-form-row">
					<label class="cp-form-label" for="edit-user-entity-type">Тип аккаунта</label>
					<select id="edit-user-entity-type" v-model="userData.entity_type" class="cp-form-select" :disabled="isSaving">
						<option value="individual">Физическое лицо</option>
						<option value="self_employed">Самозанятый</option>
						<option value="legal_entity">Юридическое лицо</option>
					</select>
				</div>

				<TextInput label="ИНН" v-model="userData.inn" placeholder="Введите ИНН" :disabled="isSaving" />
				<TextInput v-if="userData.entity_type === 'legal_entity'" label="КПП" v-model="userData.kpp" placeholder="Введите КПП" :disabled="isSaving" />
				<TextInput v-if="userData.entity_type === 'legal_entity'" label="Юридический адрес" v-model="userData.legal_address" placeholder="Введите юридический адрес" :disabled="isSaving" />

				<div class="cp-form-row cp-form-row--wide">
					<label class="cp-checkbox-row">
						<input v-model="userData.is_staff" type="checkbox" :disabled="isSaving" />
						<span>
							<strong>Сотрудник WB Insight</strong>
							<small>Включает служебные поля. Доступ всё равно определяется ролями.</small>
						</span>
					</label>
				</div>

				<template v-if="userData.is_staff">
					<TextInput label="ID сотрудника" v-model="userData.staff_id" placeholder="Например, EMP-001" :disabled="isSaving" />
					<TextInput label="Отдел" v-model="userData.department" placeholder="Поддержка / Аналитика / Продажи" :disabled="isSaving" />
					<TextInput label="Должность" v-model="userData.position" placeholder="Должность сотрудника" :disabled="isSaving" />
				</template>
			</div>

			<div
				v-if="props.currentUser && userData.email.trim().toLowerCase() !== String(props.currentUser.email || '').trim().toLowerCase()"
				class="cp-inline-notice"
			>
				<strong>Email будет считаться неподтверждённым.</strong>
				<span>После сохранения потребуется обычное подтверждение письмом либо ручная верификация администратором.</span>
			</div>

			<FormMessage v-if="formMessage" :message="formMessage" :message-type="msgStatus" />
		</template>

		<template #footer>
			<div class="cp-modal-footer">
				<BaseButton variant="outline" text="Отмена" :disabled="isSaving" @click="$emit('close')" />
				<BaseButton variant="primary" text="Сохранить" loading-text="Сохраняем…" :loading="isSaving" @click="saveUser" />
			</div>
		</template>
	</Modal>
</template>

<style scoped>
.cp-form-row--wide {
	grid-column: 1 / -1;
}

.cp-checkbox-row {
	display: flex;
	align-items: flex-start;
	gap: 10px;
	padding: 12px;
	border: 1px solid var(--border-color);
	border-radius: 10px;
	background: var(--light-bg);
	cursor: pointer;
}

.cp-checkbox-row input {
	margin-top: 3px;
}

.cp-checkbox-row span {
	display: grid;
	gap: 3px;
}

.cp-checkbox-row strong {
	font-size: 13px;
}

.cp-checkbox-row small {
	color: var(--text-muted);
	font-size: 11px;
	line-height: 1.4;
}

.cp-inline-notice {
	margin-top: 8px;
	padding: 12px 14px;
	display: grid;
	gap: 4px;
	border: 1px solid color-mix(in srgb, var(--warning-color) 35%, var(--border-color));
	border-radius: 10px;
	background: color-mix(in srgb, var(--warning-color) 8%, var(--card-bg));
}

.cp-inline-notice strong {
	font-size: 12px;
}

.cp-inline-notice span {
	color: var(--text-muted);
	font-size: 11px;
	line-height: 1.45;
}
</style>
