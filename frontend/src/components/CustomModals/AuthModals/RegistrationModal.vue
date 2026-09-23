<template>
	<Modal :is-open="isOpen" @close="$emit('close')">
		<template #header>
			<div class="registration-header">
				<h3 class="modal-title">Регистрация</h3>
				<button class="modal-close" @click="$emit('close')">&times;</button>

				<!-- Прогресс-бар -->
				<div class="registration-progress">
					<div class="progress-steps">
						<div v-for="(step, index) in steps" :key="step.key" class="step-item" :class="{
							'active': currentStep === index,
							'completed': currentStep > index
						}" @click="goToStep(index)">
							<div class="step-number">{{ index + 1 }}</div>
							<div class="step-label">{{ step.label }}</div>
						</div>
					</div>
					<div class="progress-bar">
						<div class="progress-fill" :style="{ width: progressPercentage + '%' }"></div>
					</div>
				</div>
			</div>
		</template>

		<template #body>
			<!-- Шаг 1: Тип пользователя -->
			<div v-if="currentStep === 0" class="registration-step">
				<div class="step-content">
					<h4 class="step-title">Выберите тип пользователя</h4>
					<p class="step-description">Вы регистрируетесь как:</p>

					<div class="entity-type-options">
						<div v-for="type in entityTypes" :key="type.value" class="entity-type-card"
							:class="{ 'selected': formData.entity_type === type.value }"
							@click="selectEntityType(type.value)">
							<div class="entity-type-icon">
								<i :class="type.icon"></i>
							</div>
							<div class="entity-type-info">
								<h5>{{ type.label }}</h5>
								<p>{{ type.description }}</p>
							</div>
						</div>
					</div>

					<div class="step-note">
						<i class="fa fa-info-circle"></i>
						<span>Вы сможете изменить тип позже в настройках профиля</span>
					</div>
				</div>
			</div>

			<!-- Шаг 2: Основная информация -->
			<div v-if="currentStep === 1" class="registration-step">
				<div class="step-content">
					<h4 class="step-title">Основная информация</h4>
					<p class="step-description">Заполните основные данные для регистрации</p>

					<div class="form-grid">
						<div class="form-group" :class="{ 'error': errors.full_name }">
							<label class="form-label required">
								{{ formData.entity_type === 'legal_entity' ? 'Название компании' : 'ФИО' }}
							</label>
							<input type="text" class="form-input" v-model="formData.full_name"
								:placeholder="formData.entity_type === 'legal_entity' ? 'ООО «Ромашка»' : 'Иванов Иван Иванович'"
								@blur="validateField('full_name')">
							<div v-if="errors.full_name" class="error-message">
								{{ errors.full_name }}
							</div>
						</div>

						<div class="form-group" :class="{ 'error': errors.email }">
							<label class="form-label required">Email</label>
							<input type="email" class="form-input" v-model="formData.email"
								placeholder="example@domain.com" @blur="validateEmail">
							<div v-if="errors.email" class="error-message">
								{{ errors.email }}
							</div>
						</div>

						<div class="form-group" :class="{ 'error': errors.phone }">
							<label class="form-label required">Телефон</label>
							<div class="phone-input">
								<div class="phone-prefix">+7</div>
								<input type="tel" inputmode="numeric" pattern="[0-9]*" maxlength="10" class="form-input"
									v-model="formData.phone" @input="formatPhone" @blur="validatePhone"
									placeholder="9ХХ ХХХ ХХ ХХ" />
							</div>
							<div v-if="errors.phone" class="error-message">
								{{ errors.phone }}
							</div>
						</div>


					</div>
				</div>
			</div>

			<!-- Шаг 3: Пароль -->
			<div v-if="currentStep === 2" class="registration-step">
				<div class="form-group" :class="{ 'error': errors.password }">
					<label class="form-label required">Пароль</label>
					<div class="password-input">
						<input :type="showPassword ? 'text' : 'password'" class="form-input" v-model="formData.password"
							placeholder="Минимум 8 символов" @input="validatePassword">
						<button type="button" class="password-toggle" @click="showPassword = !showPassword"
							:title="showPassword ? 'Скрыть пароль' : 'Показать пароль'">
							<i :class="showPassword ? 'fa fa-eye-slash' : 'fa fa-eye'"></i>
						</button>
					</div>
					<div v-if="errors.password" class="error-message">
						{{ errors.password }}
					</div>

					<div class="password-strength">
						<div class="strength-label">Надёжность пароля:</div>
						<div class="strength-bar">
							<div class="strength-fill" :class="passwordStrengthClass"
								:style="{ width: passwordStrength + '%' }"></div>
						</div>
						<div class="strength-hints">
							<div class="hint" :class="{ 'valid': passwordHasMinLength }">
								<i :class="passwordHasMinLength ? 'fa fa-check' : 'fa fa-circle'"></i>
								<span>8+ символов</span>
							</div>
							<div class="hint" :class="{ 'valid': passwordHasUppercase }">
								<i :class="passwordHasUppercase ? 'fa fa-check' : 'fa fa-circle'"></i>
								<span>Заглавная буква</span>
							</div>
							<div class="hint" :class="{ 'valid': passwordHasNumber }">
								<i :class="passwordHasNumber ? 'fa fa-check' : 'fa fa-circle'"></i>
								<span>Цифра</span>
							</div>
							<div class="hint" :class="{ 'valid': passwordHasSpecial }">
								<i :class="passwordHasSpecial ? 'fa fa-check' : 'fa fa-circle'"></i>
								<span>Спецсимвол</span>
							</div>
						</div>
					</div>
				</div>

				<div class="form-group" :class="{ 'error': errors.password_confirmation }">
					<label class="form-label required">Подтверждение пароля</label>
					<input :type="showConfirmPassword ? 'text' : 'password'" class="form-input"
						v-model="formData.password_confirmation" placeholder="Повторите пароль"
						@blur="validatePasswordConfirmation">
					<div v-if="errors.password_confirmation" class="error-message">
						{{ errors.password_confirmation }}
					</div>
				</div>
			</div>

			<!-- Шаг 3: Реквизиты компании (для юрлиц) или доп. информация -->
			<div v-if="currentStep === 3" class="registration-step">
				<div class="step-content">
					<template v-if="isLegalEntity">
						<h4 class="step-title">Реквизиты компании</h4>
						<p class="step-description">Заполните юридические данные организации</p>

						<div class="form-grid">
							<div class="form-group" :class="{ 'error': errors.inn }">
								<label class="form-label required">ИНН</label>
								<input type="text" class="form-input" v-model="formData.inn"
									placeholder="10 цифр для юрлиц, 12 для ИП" @input="formatInn" @blur="validateInn">
								<div v-if="errors.inn" class="error-message">
									{{ errors.inn }}
								</div>
								<div class="form-hint">Обязательно для юридических лиц</div>
							</div>

							<div class="form-group" :class="{ 'error': errors.kpp }">
								<label class="form-label">КПП</label>
								<input type="text" class="form-input" v-model="formData.kpp" placeholder="9 цифр"
									@input="formatKpp" @blur="validateKpp">
								<div v-if="errors.kpp" class="error-message">
									{{ errors.kpp }}
								</div>
								<div class="form-hint">Только для юридических лиц</div>
							</div>

							<div class="form-group full-width" :class="{ 'error': errors.legal_address }">
								<label class="form-label required">Юридический адрес</label>
								<textarea class="form-input" v-model="formData.legal_address" rows="3"
									placeholder="Город, улица, дом, офис, индекс"
									@blur="validateField('legal_address')"></textarea>
								<div v-if="errors.legal_address" class="error-message">
									{{ errors.legal_address }}
								</div>
							</div>

						</div>
					</template>

					<template v-else>
						<h4 class="step-title">Дополнительная информация</h4>
						<p class="step-description">Укажите дополнительные данные</p>

						<div class="form-grid">
							<div class="form-group" :class="{ 'error': errors.inn }">
								<label class="form-label">ИНН (опционально)</label>
								<input type="text" class="form-input" v-model="formData.inn"
									placeholder="12 цифр для физлиц" @input="formatInn" @blur="validateInn">
								<div v-if="errors.inn" class="error-message">
									{{ errors.inn }}
								</div>
								<div class="form-hint">Рекомендуем указать для налоговой отчётности</div>
							</div>

							<div class="form-group full-width">
								<label class="form-label">Часовой пояс</label>
								<div class="select-wrapper">
									<i class="fa fa-globe"></i>
									<select class="form-select" v-model="formData.timezone">
										<option value="Europe/Moscow">Москва (MSK, UTC+3)</option>
										<option value="Europe/Kaliningrad">Калининград (UTC+2)</option>
										<option value="Asia/Yekaterinburg">Екатеринбург (UTC+5)</option>
										<option value="Asia/Omsk">Омск (UTC+6)</option>
										<option value="Asia/Krasnoyarsk">Красноярск (UTC+7)</option>
										<option value="Asia/Irkutsk">Иркутск (UTC+8)</option>
										<option value="Asia/Yakutsk">Якутск (UTC+9)</option>
										<option value="Asia/Vladivostok">Владивосток (UTC+10)</option>
										<option value="Asia/Magadan">Магадан (UTC+11)</option>
										<option value="Asia/Kamchatka">Камчатка (UTC+12)</option>
									</select>
								</div>
							</div>

							<div class="form-group full-width">
								<label class="checkbox">
									<input type="checkbox" v-model="formData.newsletter_subscription">
									<span>Подписаться на новости и акции</span>
								</label>
							</div>
						</div>
					</template>
				</div>
			</div>

			<!-- Шаг 4: Соглашения -->
			<div v-if="currentStep === 4" class="registration-step">
				<div class="step-content">
					<h4 class="step-title">Соглашения</h4>
					<p class="step-description">Для завершения регистрации примите условия</p>

					<div class="agreements-container">
						<div class="agreement-card">
							<h5>Пользовательское соглашение</h5>
							<div class="agreement-content">
								<p>Ознакомьтесь с условиями использования сервиса Wildberries.</p>
								<a href="/terms" target="_blank" class="agreement-link">
									<i class="fa fa-external-link"></i>
									Открыть полный текст
								</a>
							</div>
							<div class="agreement-checkbox">
								<input type="checkbox" id="terms-agreement" v-model="formData.agree_terms"
									class="checkbox-input">
								<label for="terms-agreement" class="checkbox-label">
									Я принимаю условия <a href="/terms" target="_blank" class="link">Пользовательского
										соглашения</a>
								</label>
							</div>
						</div>

						<div class="agreement-card">
							<h5>Политика конфиденциальности</h5>
							<div class="agreement-content">
								<p>Узнайте, как мы обрабатываем ваши персональные данные.</p>
								<a href="/privacy" target="_blank" class="agreement-link">
									<i class="fa fa-external-link"></i>
									Открыть полный текст
								</a>
							</div>
							<div class="agreement-checkbox">
								<input type="checkbox" id="privacy-agreement" v-model="formData.agree_privacy"
									class="checkbox-input">
								<label for="privacy-agreement" class="checkbox-label">
									Я согласен с <a href="/privacy" target="_blank" class="link">Политикой
										конфиденциальности</a>
								</label>
							</div>
						</div>

						<div v-if="isLegalEntity" class="agreement-card">
							<h5>Обработка персональных данных</h5>
							<div class="agreement-content">
								<p>Согласие на обработку персональных данных сотрудников и контрагентов.</p>
							</div>
							<div class="agreement-checkbox">
								<input type="checkbox" id="data-processing" v-model="formData.agree_data_processing"
									class="checkbox-input">
								<label for="data-processing" class="checkbox-label">
									Я даю согласие на обработку персональных данных
								</label>
							</div>
						</div>

						<div class="agreement-errors" v-if="hasAgreementErrors">
							<i class="fa fa-exclamation-circle"></i>
							<span>Необходимо принять все условия для продолжения</span>
						</div>
					</div>
				</div>
			</div>
		</template>

		<template #footer>
			<div class="registration-footer">
				<div class="step-info">
					<span class="step-counter">Шаг {{ currentStep + 1 }} из {{ steps.length }}</span>
				</div>
				<div class="step-actions">
					<ButtonOutline v-if="currentStep > 0" @click="prevStep" :disabled="isLoading">
						<i class="fa fa-arrow-left"></i>
						Назад
					</ButtonOutline>

					<ButtonPrimary v-if="currentStep < steps.length - 1" @click="nextStep"
						:disabled="!canProceed || isLoading">
						Далее
						<i class="fa fa-arrow-right"></i>
					</ButtonPrimary>

					<ButtonSuccess v-if="currentStep === steps.length - 1" @click="performRegistration"
						:disabled="!canSubmit || isLoading">
						<span v-if="isLoading">
							<i class="fa fa-spinner fa-spin"></i>
							Регистрация...
						</span>
						<span v-else>
							<i class="fa fa-check"></i>
							Зарегистрироваться
						</span>
					</ButtonSuccess>
				</div>
			</div>
		</template>
	</Modal>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import Modal from '@/components/UI/Modal.vue'
import AuthService from '@/API/AuthService.js'
import ButtonPrimary from '@/components/UI/Buttons/ButtonPrimary.vue'
import ButtonOutline from '@/components/UI/Buttons/ButtonOutline.vue'
import ButtonSuccess from '@/components/UI/Buttons/ButtonSuccess.vue'

import { notify } from '@/composables/notification';

const props = defineProps({
	isOpen: Boolean
})

const emit = defineEmits(['close', 'switch-to-login', 'success'])

// Состояние
const currentStep = ref(0)
const isLoading = ref(false)
const showPassword = ref(false)
const showConfirmPassword = ref(false)

// Данные формы
const formData = ref({
	// Шаг 1
	entity_type: '',

	// Шаг 2
	full_name: '',
	email: '',
	phone: '',
	password: '',
	password_confirmation: '',

	// Шаг 3
	inn: '',
	kpp: '',
	legal_address: '',
	timezone: 'Europe/Moscow',
	newsletter_subscription: true,

	// Шаг 4
	agree_terms: false,
	agree_privacy: false,
	agree_data_processing: false
})

// Ошибки
const errors = ref({})

// Шаги регистрации
const steps = computed(() => {
	const baseSteps = [
		{ key: 'entity_type', label: 'Тип пользователя' },
		{ key: 'basic_info', label: 'Основная информация' },
		{ key: 'password', label: 'Пароль' }
	]

	if (isLegalEntity.value) {
		baseSteps.push(
			{ key: 'company_info', label: 'Реквизиты компании' },
			{ key: 'agreements', label: 'Соглашения' }
		)
	} else {
		baseSteps.push(
			{ key: 'additional_info', label: 'Дополнительно' },
			{ key: 'agreements', label: 'Соглашения' }
		)
	}

	return baseSteps
})

// Типы пользователей
const entityTypes = [
	{
		value: 'individual',
		label: 'Физическое лицо',
		description: 'Покупки для себя, возврат НДС',
		icon: 'fa fa-user'
	},
	{
		value: 'self_employed',
		label: 'Самозанятый / ИП',
		description: 'Ведение бизнеса, онлайн-касса',
		icon: 'fa fa-black-tie'
	},
	{
		value: 'legal_entity',
		label: 'Юридическое лицо',
		description: 'Компании, ООО, корпоративные закупки',
		icon: 'fa fa-building'
	}
]

// Вычисляемые свойства
const progressPercentage = computed(() => {
	return ((currentStep.value + 1) / steps.value.length) * 100
})

const isLegalEntity = computed(() => {
	return formData.value.entity_type === 'legal_entity'
})

const canProceed = computed(() => {
	switch (currentStep.value) {
		case 0:
			return !!formData.value.entity_type
		case 1:
			return validateStep1()
		case 2:
			return validateStep2()
		case 3:
			return validateStep3()
		default:
			return true
	}
})

const canSubmit = computed(() => {
	const agreements = [formData.value.agree_terms, formData.value.agree_privacy]
	if (isLegalEntity.value) {
		agreements.push(formData.value.agree_data_processing)
	}
	return agreements.every(Boolean) && canProceed.value
})

const hasAgreementErrors = computed(() => {
	return currentStep.value === steps.value.length - 1 && !canSubmit.value
})

// Проверки пароля
const passwordHasMinLength = computed(() => formData.value.password.length >= 8)
const passwordHasUppercase = computed(() => /[A-ZА-Я]/.test(formData.value.password))
const passwordHasLowercase = computed(() => /[a-zа-я]/.test(formData.value.password))
const passwordHasNumber = computed(() => /\d/.test(formData.value.password))
const passwordHasSpecial = computed(() => /[!@#$%^&*(),.?":{}|<>]/.test(formData.value.password))

const passwordStrength = computed(() => {
	let strength = 0
	if (passwordHasMinLength.value) strength += 20
	if (passwordHasUppercase.value) strength += 20
	if (passwordHasLowercase.value) strength += 20
	if (passwordHasNumber.value) strength += 20
	if (passwordHasSpecial.value) strength += 20
	return Math.min(strength, 100)
})

const passwordStrengthClass = computed(() => {
	if (passwordStrength.value < 40) return 'weak'
	if (passwordStrength.value < 70) return 'medium'
	return 'strong'
})

// Методы
const handleClose = () => {
	resetForm()
	emit('close')
}

const resetForm = () => {
	currentStep.value = 0
	errors.value = {}
	Object.keys(formData.value).forEach(key => {
		if (key === 'timezone') {
			formData.value[key] = 'Europe/Moscow'
		} else if (key === 'newsletter_subscription') {
			formData.value[key] = true
		} else if (typeof formData.value[key] === 'boolean') {
			formData.value[key] = false
		} else {
			formData.value[key] = ''
		}
	})
}

const selectEntityType = (type) => {
	formData.value.entity_type = type
}

const nextStep = () => {
	if (canProceed.value) {
		currentStep.value++
	}
}

const prevStep = () => {
	currentStep.value--
}

const goToStep = (index) => {
	if (index <= currentStep.value) {
		currentStep.value = index
	}
}

// Валидация
const validateStep1 = () => {
	const { full_name, email, phone } = formData.value

	let isValid = true

	if (!full_name.trim()) {
		errors.value.full_name = 'Обязательное поле'
		isValid = false
	}

	if (!email.trim() || errors.value.email) {
		isValid = false
	}

	if (!phone.trim() || errors.value.phone) {
		isValid = false
	}

	return isValid
}

const validateStep2 = () => {
	const fields = ['password', 'password_confirmation']
	let isValid = true
	fields.forEach(field => {
		if (!formData.value[field]) {
			errors.value[field] = 'Обязательное поле'
			isValid = false
		}
	})

	if (formData.value.password !== formData.value.password_confirmation) {
		errors.value.password_confirmation = 'Пароли не совпадают'
		isValid = false
	}

	if (formData.value.password && formData.value.password.length < 8) {
		errors.value.password = 'Пароль должен содержать минимум 8 символов'
		isValid = false
	}

	return isValid
}

const validateStep3 = () => {
	if (isLegalEntity.value) {
		if (!formData.value.inn) {
			errors.value.inn = 'ИНН обязателен для юрлиц'
			return false
		}
		if (!formData.value.legal_address) {
			errors.value.legal_address = 'Юридический адрес обязателен'
			return false
		}
		if (formData.value.inn && formData.value.inn.length !== 10) {
			errors.value.inn = 'ИНН юрлица должен содержать 10 цифр'
			return false
		}
	}
	return true
}

const validateField = (field) => {
	if (!formData.value[field]) {
		errors.value[field] = 'Это поле обязательно'
	} else {
		delete errors.value[field]
	}
}

const validateEmail = async () => {
	const email = formData.value.email.trim()
	const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
	errors.value.email = '';
	if (!email) {
		errors.value.email = 'Email обязателен'
		return
	}

	if (!emailRegex.test(email)) {
		errors.value.email = 'Введите корректный email'
		return
	}

	// Проверка уникальности
	try {
		const response = await AuthService.checkEmail(email);
		if (response.data.status == "error") {
			errors.value.email = response.data.error.message
				? response.data.error.message
				: "Этот email уже зарегистрирован";
		}

	} catch (error) {
		errors.value.email = 'Не удалось проверить email. Повторите попытку.'
		console.error('Ошибка проверки email:', error)
	}
}

const validatePhone = async () => {
	const phone = formData.value.phone.replace(/\D/g, '')

	errors.value.phone = ''

	if (!phone) {
		errors.value.phone = 'Телефон обязателен'
		return
	}

	if (phone.length !== 10) {
		errors.value.phone = 'Введите корректный номер телефона'
		return
	}

	try {
		const response = await AuthService.checkPhone(phone)

		if (response.data.status === "error") {
			errors.value.phone = response.data.error.message
				? response.data.error.message
				: "Этот номер телефона уже зарегистрирован"
			return
		}

		// ✅ только если всё ок
		delete errors.value.phone

	} catch (error) {
		errors.value.phone = 'Не удалось проверить номер телефона. Повторите попытку.'
		console.error('Ошибка проверки номера телефона:', error)
	}
}

const validatePassword = () => {
	if (!formData.value.password) {
		errors.value.password = 'Пароль обязателен'
	} else if (formData.value.password.length < 8) {
		errors.value.password = 'Минимум 8 символов'
	} else {
		delete errors.value.password
	}
}

const validatePasswordConfirmation = () => {
	if (!formData.value.password_confirmation) {
		errors.value.password_confirmation = 'Подтвердите пароль'
	} else if (formData.value.password !== formData.value.password_confirmation) {
		errors.value.password_confirmation = 'Пароли не совпадают'
	} else {
		delete errors.value.password_confirmation
	}
}

const validateInn = async () => {
	const inn = formData.value.inn.replace(/\D/g, '')
	if (!inn && isLegalEntity.value) {
		errors.value.inn = 'ИНН обязателен для юрлиц'
	} else if (inn && isLegalEntity.value && inn.length !== 10) {
		errors.value.inn = 'ИНН юрлица должен содержать 10 цифр'
	} else if (inn && !isLegalEntity.value && inn.length !== 12) {
		errors.value.inn = 'ИНН физлица должен содержать 12 цифр'
	}

	if (!inn) return
	if (errors.value.inn) return

	try {
		const response = await AuthService.checkInn(inn);
		if (response.data.status == "error") {
			errors.value.inn = response.data.error.message
				? response.data.error.message
				: "Этот ИНН уже зарегистрирован";
		}
	} catch (error) {
		errors.value.inn = 'Не удалось проверить ИНН. Повторите попытку.'
		console.error('Ошибка проверки ИНН:', error)
	}
}

const validateKpp = () => {
	const kpp = formData.value.kpp.replace(/\D/g, '')
	if (kpp && kpp.length !== 9) {
		errors.value.kpp = 'КПП должен содержать 9 цифр'
	} else {
		delete errors.value.kpp
	}
}

// Форматирование
const formatPhone = (event) => {
	let value = event.target.value.replace(/\D/g, '');
	if (value.length >= 10) {
		value = value.slice(0, 10)
		value = `${value.slice(0, 3)} ${value.slice(3, 6)} ${value.slice(6, 8)} ${value.slice(8, 10)}`
	}
	formData.value.phone = value;
};

const formatInn = (event) => {
	let value = event.target.value.replace(/\D/g, '')
	if (isLegalEntity.value && value.length > 10) value = value.substring(0, 10)
	if (!isLegalEntity.value && value.length > 12) value = value.substring(0, 12)
	formData.value.inn = value
}

const formatKpp = (event) => {
	let value = event.target.value.replace(/\D/g, '')
	if (value.length > 9) value = value.substring(0, 9)
	formData.value.kpp = value
}


// Регистрация
const performRegistration = async () => {
	if (!canSubmit.value || isLoading.value) return

	isLoading.value = true

	try {
		// Подготовка данных
		const registrationData = {
			...formData.value,
			phone: '+7' + formData.value.phone.replace(/\D/g, ''),
			inn: formData.value.inn.replace(/\D/g, ''),
			kpp: formData.value.kpp.replace(/\D/g, '')
		}

		// Удаляем подтверждение пароля из отправляемых данных
		delete registrationData.password_confirmation

		//const response = await axios.post('/api/auth/register', registrationData)
		const response = await AuthService.registration(registrationData)

		if (response.data.status === 'success') {
			// Автоматически логиним
			/* await authStore.login({
				email: formData.value.email,
				password: formData.value.password
			}) */

			emit('success')
			handleClose()

			// Показываем welcome сообщение
			setTimeout(() => {
				/* alert('Регистрация успешна! Добро пожаловать в систему.') */
				notify.success('Регистрация успешна!')
			}, 300)
		}

		if (response.data.status === 'error') {
			notify.error(response.data.error.message)
		}

	} catch (error) {
		console.error('Ошибка регистрации:', error)
		notify.error(error)

		// Возвращаемся к шагу с ошибками
		currentStep.value = 1

	} finally {
		isLoading.value = false
	}
}

const switchToLogin = () => {
	handleClose()
	emit('switch-to-login')
}

// Следим за изменениями
watch(() => props.isOpen, (newValue) => {
	if (!newValue) {
		resetForm()
	}
})
</script>

<style scoped>
.registration-header {
	padding: 20px 20px 10px 20px;
	display: flex;
	flex-direction: column;
	gap: 15px;
}

.modal-title {
	font-size: 20px;
	font-weight: 600;
	margin: 0;
}

.modal-close {
	background: none;
	border: none;
	font-size: 24px;
	cursor: pointer;
	color: #aaa;
	padding: 0;
	width: 30px;
	height: 30px;
	display: flex;
	align-items: center;
	justify-content: center;
	position: absolute;
	right: 20px;
	top: 20px;
}

/* Прогресс-бар */
.registration-progress {
	margin-top: 10px;
}

.progress-steps {
	display: flex;
	justify-content: space-between;
	margin-bottom: 8px;
}

.step-item {
	display: flex;
	flex-direction: column;
	align-items: center;
	cursor: pointer;
	flex: 1;
	position: relative;
	z-index: 1;
}

.step-item:not(:last-child)::after {
	content: '';
	position: absolute;
	top: 15px;
	right: -50%;
	width: 100%;
	height: 2px;
	background-color: var(--border-color);
	z-index: 1;
}

.step-item.completed:not(:last-child)::after {
	background-color: var(--secondary-color);
}

.step-number {
	width: 30px;
	height: 30px;
	border-radius: 50%;
	background-color: var(--light-bg);
	border: 2px solid var(--border-color);
	display: flex;
	align-items: center;
	justify-content: center;
	font-weight: 600;
	font-size: 14px;
	margin-bottom: 6px;
	z-index: 2;
	transition: all 0.3s;
}

.step-item.active .step-number {
	background-color: var(--secondary-color);
	border-color: var(--secondary-color);
	color: white;
}

.step-item.completed .step-number {
	background-color: var(--secondary-color);
	border-color: var(--secondary-color);
	color: white;
}

.step-label {
	font-size: 12px;
	color: var(--text-secondary);
	text-align: center;
	transition: all 0.3s;
}

.step-item.active .step-label {
	color: var(--text-color);
	font-weight: 500;
}

.progress-bar {
	height: 4px;
	background-color: var(--light-bg);
	border-radius: 2px;
	overflow: hidden;
}

.progress-fill {
	height: 100%;
	background-color: var(--secondary-color);
	border-radius: 2px;
	transition: width 0.3s ease;
}

/* Шаги регистрации */
.registration-step {
	padding: 15px;
}

.step-content {
	animation: fadeIn 0.3s ease;
}

.step-title {
	font-size: 18px;
	font-weight: 600;
	margin-bottom: 8px;
	color: var(--text-color);
}

.step-description {
	color: var(--text-secondary);
	margin-bottom: 15px;
	font-size: 14px;
}

.step-note {
	display: flex;
	align-items: center;
	gap: 8px;
	color: var(--text-secondary);
	font-size: 14px;
	margin-top: 20px;
	padding: 12px;
	background-color: rgba(52, 152, 219, 0.1);
	border-radius: 6px;
}

.step-note i {
	color: var(--secondary-color);
}

/* Типы пользователей */
.entity-type-options {
	display: flex;
	flex-direction: column;
	gap: 12px;
	margin: 20px 0;
}

.entity-type-card {
	display: flex;
	align-items: center;
	gap: 15px;
	padding: 15px;
	border: 2px solid var(--border-color);
	border-radius: 8px;
	cursor: pointer;
	transition: all 0.2s;
}

.entity-type-card:hover {
	border-color: var(--secondary-color);
	background-color: rgba(52, 152, 219, 0.05);
}

.entity-type-card.selected {
	border-color: var(--secondary-color);
	background-color: rgba(52, 152, 219, 0.1);
}

.entity-type-icon {
	width: 40px;
	height: 40px;
	display: flex;
	align-items: center;
	justify-content: center;
	background-color: var(--light-bg);
	border-radius: 6px;
	font-size: 18px;
	color: var(--text-color);
}

.entity-type-card.selected .entity-type-icon {
	background-color: var(--secondary-color);
	color: white;
}

.entity-type-info h5 {
	margin: 0 0 4px 0;
	font-weight: 600;
	font-size: 16px;
	color: var(--text-color);
}

.entity-type-info p {
	margin: 0;
	font-size: 14px;
	color: var(--text-secondary);
}

/* Форма */
.form-grid {
	display: flex;
	flex-direction: column;
	gap: 20px;
}

.form-group {
	margin-bottom: 0;
}

.form-group.full-width {
	width: 100%;
}

.form-label {
	display: block;
	margin-bottom: 8px;
	font-weight: 500;
	font-size: 14px;
	color: var(--text-color);
}

.form-label.required::after {
	content: ' *';
	color: var(--accent-color);
}

.form-input {
	width: 100%;
	padding: 12px;
	border: 1px solid var(--border-color);
	border-radius: 6px;
	background-color: var(--medium-bg);
	color: var(--text-color);
	font-size: 14px;
	transition: all 0.2s;
}

.form-input:focus {
	outline: none;
	border-color: var(--secondary-color);
}

.form-group.error .form-input {
	border-color: var(--accent-color);
}

.error-message {
	color: var(--accent-color);
	font-size: 12px;
	margin-top: 4px;
}

.form-hint {
	color: var(--text-secondary);
	font-size: 12px;
	margin-top: 4px;
}

/* Phone input */
.phone-input {
	display: flex;
}

.phone-prefix {
	background-color: var(--light-bg);
	border: 1px solid var(--border-color);
	border-right: none;
	border-radius: 6px 0 0 6px;
	padding: 12px 15px;
	color: var(--text-secondary);
	font-size: 14px;
	display: flex;
	align-items: center;
}

.phone-input .form-input {
	border-radius: 0 6px 6px 0;
	flex: 1;
}

/* Password input */
.password-input {
	position: relative;
}

.password-toggle {
	position: absolute;
	right: 12px;
	top: 50%;
	transform: translateY(-50%);
	background: none;
	border: none;
	color: var(--text-secondary);
	cursor: pointer;
	padding: 4px;
	font-size: 16px;
}

.password-toggle:hover {
	color: var(--text-color);
}

/* Password strength */
.password-strength {
	margin-top: 10px;
}

.strength-label {
	font-size: 12px;
	color: var(--text-secondary);
	margin-bottom: 6px;
}

.strength-bar {
	height: 6px;
	background-color: var(--light-bg);
	border-radius: 3px;
	overflow: hidden;
	margin-bottom: 8px;
}

.strength-fill {
	height: 100%;
	border-radius: 3px;
	transition: width 0.3s;
}

.strength-fill.weak {
	background-color: var(--accent-color);
}

.strength-fill.medium {
	background-color: var(--warning-color);
}

.strength-fill.strong {
	background-color: var(--success-color);
}

.strength-hints {
	display: grid;
	grid-template-columns: repeat(2, 1fr);
	gap: 8px;
}

.hint {
	display: flex;
	align-items: center;
	gap: 6px;
	font-size: 12px;
	color: var(--text-secondary);
}

.hint i {
	font-size: 10px;
}

.hint.valid {
	color: var(--success-color);
}

.hint.valid i {
	color: var(--success-color);
}

/* Select */
.select-wrapper {
	position: relative;
}

.select-wrapper i {
	position: absolute;
	left: 12px;
	top: 50%;
	transform: translateY(-50%);
	color: var(--text-secondary);
	pointer-events: none;
}

.form-select {
	width: 100%;
	padding: 12px 12px 12px 40px;
	border: 1px solid var(--border-color);
	border-radius: 6px;
	background-color: var(--medium-bg);
	color: var(--text-color);
	font-size: 14px;
	appearance: none;
	cursor: pointer;
}

.form-select:focus {
	outline: none;
	border-color: var(--secondary-color);
}

/* Textarea */
textarea.form-input {
	resize: vertical;
	min-height: 80px;
	font-family: inherit;
}

/* Checkbox */
.checkbox {
	display: flex;
	align-items: center;
	gap: 10px;
	cursor: pointer;
	font-size: 14px;
	color: var(--text-color);
}

.checkbox input[type="checkbox"] {
	width: 18px;
	height: 18px;
	border: 2px solid var(--border-color);
	border-radius: 4px;
	cursor: pointer;
}

.checkbox input[type="checkbox"]:checked {
	background-color: var(--secondary-color);
	border-color: var(--secondary-color);
}

/* Agreements */
.agreements-container {
	display: flex;
	flex-direction: column;
	gap: 15px;
}

.agreement-card {
	border: 1px solid var(--border-color);
	border-radius: 8px;
	padding: 15px;
	background-color: var(--card-bg);
}

.agreement-card h5 {
	margin: 0 0 10px 0;
	font-size: 16px;
	font-weight: 600;
	color: var(--text-color);
}

.agreement-content {
	margin-bottom: 15px;
}

.agreement-content p {
	margin: 0 0 8px 0;
	font-size: 14px;
	color: var(--text-secondary);
}

.agreement-link {
	display: inline-flex;
	align-items: center;
	gap: 6px;
	font-size: 14px;
	color: var(--secondary-color);
	text-decoration: none;
}

.agreement-link:hover {
	text-decoration: underline;
}

.agreement-checkbox {
	display: flex;
	align-items: flex-start;
	gap: 10px;
}

.checkbox-input {
	width: 18px;
	height: 18px;
	margin-top: 2px;
	cursor: pointer;
}

.checkbox-label {
	font-size: 14px;
	color: var(--text-color);
	line-height: 1.4;
}

.checkbox-label .link {
	color: var(--secondary-color);
	text-decoration: none;
}

.checkbox-label .link:hover {
	text-decoration: underline;
}

.agreement-errors {
	display: flex;
	align-items: center;
	gap: 8px;
	color: var(--accent-color);
	font-size: 14px;
	padding: 12px;
	background-color: rgba(231, 76, 60, 0.1);
	border-radius: 6px;
	margin-top: 10px;
}

/* Footer */
.registration-footer {
	display: flex;
	justify-content: space-between;
	align-items: center;
	padding: 20px;
	border-top: 1px solid var(--border-color);
}

.step-info {
	font-size: 14px;
	color: var(--text-secondary);
}

.step-actions {
	display: flex;
	gap: 10px;
}

/* Анимации */
@keyframes fadeIn {
	from {
		opacity: 0;
		transform: translateY(10px);
	}

	to {
		opacity: 1;
		transform: translateY(0);
	}
}

/* Адаптивность */
@media (max-width: 768px) {
	.registration-header {
		padding: 15px 15px 10px 15px;
	}

	.modal-close {
		right: 15px;
		top: 15px;
	}

	.registration-step {
		padding: 15px;
	}

	.step-title {
		font-size: 16px;
	}

	.entity-type-card {
		padding: 12px;
	}

	.entity-type-icon {
		width: 35px;
		height: 35px;
		font-size: 16px;
	}

	.form-grid {
		gap: 15px;
	}

	.form-input {
		padding: 10px;
	}

	.agreement-card {
		padding: 12px;
	}

	.registration-footer {
		padding: 15px;
		flex-direction: column;
		gap: 15px;
		align-items: stretch;
	}

	.step-actions {
		width: 100%;
	}

	.step-actions button {
		flex: 1;
	}
}

@media (max-width: 480px) {
	.step-label {
		font-size: 10px;
	}

	.step-number {
		width: 25px;
		height: 25px;
		font-size: 12px;
	}

	.entity-type-info h5 {
		font-size: 14px;
	}

	.entity-type-info p {
		font-size: 12px;
	}

	.strength-hints {
		grid-template-columns: 1fr;
	}
}
</style>