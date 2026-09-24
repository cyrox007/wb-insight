<script setup>
import { ref } from 'vue'
import CP_Users from '@/API/ControlPanel/CP_Users'
import BaseButton from '@/components/UI/Buttons/BaseButton.vue'
import FormMessage from '@/components/UI/FormMessage.vue'
import Modal from '@/components/UI/Modal.vue'
import TextInput from '@/components/UI/TextInput.vue'

defineProps({
	isOpen: Boolean,
})

const emit = defineEmits(['close', 'created'])

const ROLE_OPTIONS = [
	{ value: 'admin', label: 'Администратор' },
	{ value: 'manager', label: 'Менеджер' },
	{ value: 'support', label: 'Поддержка' },
	{ value: 'analyst', label: 'Аналитик' },
]

const form = ref({
	full_name: '',
	email: '',
	phone: '',
	password: '',
	role: 'manager',
	timezone: 'Europe/Moscow',
	staff_id: '',
	department: '',
	position: '',
})

const isSaving = ref(false)
const formMessage = ref('')

function generatePassword() {
	const alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%&*'
	const bytes = new Uint32Array(18)
	window.crypto.getRandomValues(bytes)
	form.value.password = Array.from(bytes, value => alphabet[value % alphabet.length]).join('')
}

function validate() {
	const fullName = form.value.full_name.trim()
	const email = form.value.email.trim().toLowerCase()
	const phone = form.value.phone.trim()
	const password = form.value.password

	if (!fullName) return 'Укажите имя сотрудника.'
	if (!email || !email.includes('@')) return 'Укажите корректный email.'
	if (!phone) return 'Укажите телефон.'
	if (password.length < 8) return 'Временный пароль должен содержать минимум 8 символов.'
	if (new TextEncoder().encode(password).length > 72) return 'Временный пароль не должен превышать 72 байта.'
	if (!ROLE_OPTIONS.some(item => item.value === form.value.role)) return 'Выберите служебную роль.'
	return ''
}

async function createUser() {
	if (isSaving.value) return

	formMessage.value = validate()
	if (formMessage.value) return

	isSaving.value = true
	try {
		const response = await CP_Users.createStaffUser({
			full_name: form.value.full_name.trim(),
			email: form.value.email.trim().toLowerCase(),
			phone: form.value.phone.trim(),
			password: form.value.password,
			role: form.value.role,
			timezone: form.value.timezone.trim() || 'Europe/Moscow',
			staff_id: form.value.staff_id.trim() || null,
			department: form.value.department.trim() || null,
			position: form.value.position.trim() || null,
		})

		if (response.data?.status !== 'success' || !response.data?.user?.id) {
			throw new Error(response.data?.error?.message || 'Не удалось создать сотрудника')
		}

		emit('created', response.data.user)
		emit('close')
	} catch (error) {
		formMessage.value =
			error.response?.data?.error?.message ||
			error.message ||
			'Не удалось создать служебный аккаунт.'
	} finally {
		isSaving.value = false
	}
}
</script>

<template>
	<Modal
		:is-open="isOpen"
		size="large"
		aria-label="Создание служебного аккаунта"
		:close-on-overlay-click="!isSaving"
		:close-on-escape="!isSaving"
		@close="$emit('close')"
	>
		<template #header>
			<div>
				<h3 class="cp-modal-title">Добавить сотрудника</h3>
				<p class="cp-muted">Служебный аккаунт создаётся суперадминистратором и сразу получает выбранную роль.</p>
			</div>
		</template>

		<template #body>
			<div class="cp-form-grid" :aria-busy="isSaving">
				<TextInput v-model="form.full_name" label="Имя" placeholder="Имя сотрудника" :disabled="isSaving" />
				<TextInput v-model="form.email" label="Email" type="email" placeholder="name@example.com" :disabled="isSaving" />
				<TextInput v-model="form.phone" label="Телефон" placeholder="+79990000000" :disabled="isSaving" />
				<TextInput v-model="form.timezone" label="Часовой пояс" placeholder="Europe/Moscow" :disabled="isSaving" />

				<div class="cp-form-row">
					<label class="cp-form-label" for="create-staff-role">Роль</label>
					<select id="create-staff-role" v-model="form.role" class="cp-form-select" :disabled="isSaving">
						<option v-for="item in ROLE_OPTIONS" :key="item.value" :value="item.value">{{ item.label }}</option>
					</select>
				</div>

				<div class="cp-form-row">
					<label class="cp-form-label" for="create-staff-password">Временный пароль</label>
					<div class="password-row">
						<input
							id="create-staff-password"
							v-model="form.password"
							class="cp-form-input"
							type="text"
							autocomplete="new-password"
							placeholder="Минимум 8 символов"
							:disabled="isSaving"
						/>
						<BaseButton
							variant="outline"
							size="small"
							text="Сгенерировать"
							:disabled="isSaving"
							@click="generatePassword"
						/>
					</div>
				</div>

				<TextInput v-model="form.staff_id" label="ID сотрудника" placeholder="Например, EMP-001" :disabled="isSaving" />
				<TextInput v-model="form.department" label="Отдел" placeholder="Поддержка / Аналитика / Продажи" :disabled="isSaving" />
				<TextInput v-model="form.position" label="Должность" placeholder="Должность сотрудника" :disabled="isSaving" />
			</div>

			<div class="cp-inline-notice">
				<strong>Клиентские аккаунты здесь не создаются.</strong>
				<span>Клиент проходит обычную регистрацию самостоятельно, чтобы юридические согласия фиксировались от его имени. В панели создаются только служебные аккаунты.</span>
			</div>

			<FormMessage v-if="formMessage" :message="formMessage" message-type="error" />
		</template>

		<template #footer>
			<div class="cp-modal-footer">
				<BaseButton variant="outline" text="Отмена" :disabled="isSaving" @click="$emit('close')" />
				<BaseButton
					variant="primary"
					text="Создать сотрудника"
					loading-text="Создаём…"
					:loading="isSaving"
					@click="createUser"
				/>
			</div>
		</template>
	</Modal>
</template>

<style scoped>
.password-row {
	display: grid;
	grid-template-columns: minmax(0, 1fr) auto;
	gap: 8px;
}

.cp-inline-notice {
	margin-top: 12px;
	padding: 12px 14px;
	display: grid;
	gap: 4px;
	border: 1px solid color-mix(in srgb, var(--secondary-color) 24%, var(--border-color));
	border-radius: 10px;
	background: color-mix(in srgb, var(--secondary-color) 6%, var(--card-bg));
}

.cp-inline-notice strong {
	font-size: 12px;
}

.cp-inline-notice span {
	color: var(--text-muted);
	font-size: 11px;
	line-height: 1.45;
}

@media (max-width: 640px) {
	.password-row {
		grid-template-columns: 1fr;
	}
}
</style>
