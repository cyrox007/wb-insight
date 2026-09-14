<script setup>
import { onMounted, ref } from 'vue'
import { notify } from '@/composables/notification'
import DateTransform from '@/utils/date_transform'

import ProfileServices from '@/API/Dashboard/ProfileServices'

import ButtonSuccess from '@/components/UI/Buttons/ButtonSuccess.vue'
import SelectTariffModal from '@/components/CustomModals/ProfileModals/SelectTariffModal.vue'
import AddTokenModal from '@/components/CustomModals/ProfileModals/AddTokenModal.vue'

const user = ref({})
const subscription = ref(null)
const isLoading = ref(true)
const tokens = ref([])

const showEditProfile = ref(false)
const showAddTokenModal = ref(false)
const showTariffModal = ref(false)
const addBtnLoading = ref(false)

onMounted(async () => {
	try {
		isLoading.value = true
		const response = await ProfileServices.getProfile()

		tokens.value = response.data.tokens
		subscription.value = response.data.subscription
		user.value = response.data.user
	} catch (error) {
		console.error(error)
		notify.error('Ошибка загрузки профиля')
	} finally {
		isLoading.value = false
	}
})

const openAddTokenModal = async () => {
	addBtnLoading.value = true
	try {
		const response = await ProfileServices.checkTokenPermission(user.value.id)
		if (response.data.status === 'error') {
			notify.error(response.data.error.message)
			return
		}
		showAddTokenModal.value = true
	} catch (error) {
		notify.error(error.response?.data?.error?.message || 'Не удалось проверить лимит кабинетов')
	} finally {
		addBtnLoading.value = false
	}
}

const handleTokenAdded = async () => {
	const response = await ProfileServices.getProfile()
	tokens.value = response.data.tokens
	showAddTokenModal.value = false
	notify.success('Подключение Wildberries добавлено')
}

const deleteToken = async (id) => {
	if (!confirm('Удалить подключение? Это действие нельзя отменить.')) return

	try {
		const response = await ProfileServices.delete_user_token(id)
		if (response.data.status === 'error') {
			notify.error(response.data.error.message)
			return
		}
		tokens.value = tokens.value.filter(token => token.id !== id)
		notify.success('Подключение удалено')
	} catch (error) {
		notify.error(error.response?.data?.error?.message || 'Не удалось удалить подключение')
	}
}

const toPay = async (payment_id) => {
	location.href = `/billing/success?payment_id=${payment_id}`
}

const getStatusLabel = (status) => {
	switch (status) {
		case 'active': return 'Активна'
		case 'demo': return 'Демо'
		case 'expired': return 'Истекла'
		case 'cancelled': return 'Отменена'
		default: return 'Нет подписки'
	}
}

const isTokenExpired = (token) => {
	if (token.is_revoked || token.is_active === false || token.is_valid === false) return true
	return Boolean(token.expires_at && new Date(token.expires_at) < new Date())
}
</script>

<template>
	<div class="dashboard-container">
		<div class="profile-card">
			<div class="profile-header">
				<div class="left">
					<div class="avatar-placeholder">
						{{ user.full_name?.charAt(0) }}
					</div>

					<div class="user-info">
						<h2 class="user-name">{{ user.full_name }}</h2>
						<p class="user-email">{{ user.email }}</p>
					</div>
				</div>

				<div class="right">
					<div class="tariff-badge">
						<span class="tariff-name">{{ subscription?.tariff_name || 'DEMO' }}</span>
						<span class="tariff-status" :class="subscription?.status">
							{{ getStatusLabel(subscription?.status) }}
						</span>
						<div class="tariff-dates" v-if="subscription">
							до {{ DateTransform.formatDate(subscription.end_date) }}
						</div>
					</div>

					<button @click="showTariffModal = true" class="change-tariff-btn">
						{{ subscription?.status === 'active' ? 'Сменить тариф' : 'Продлить подписку' }}
					</button>
				</div>
			</div>

			<div class="profile-actions">
				<button @click="showEditProfile = true" class="edit-btn">
					<svg class="edit-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
							d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
					</svg>
					Редактировать профиль
				</button>
			</div>
		</div>

		<div class="account-grid">
			<div class="account-card">
				<div class="card-title">Тип аккаунта</div>
				<div class="card-value">
					{{ user.entity_type === 'individual' ? 'Физ. лицо' : 'Компания' }}
				</div>
			</div>

			<div class="account-card">
				<div class="card-title">Налог</div>
				<div class="card-value">
					{{ ((user.tax_rate || 0) * 100).toFixed(0) }}%
				</div>
			</div>

			<div class="account-card">
				<div class="card-title">Часовой пояс</div>
				<div class="card-value">
					{{ user.timezone }}
				</div>
			</div>

			<div class="account-card">
				<div class="card-title">Дата регистрации</div>
				<div class="card-value">
					{{ DateTransform.formatDate(user.created_at) }}
				</div>
			</div>
		</div>

		<div class="tokens-section">
			<div class="section-header">
				<h3>Подключения Wildberries</h3>
				<ButtonSuccess :loading="addBtnLoading" @click="openAddTokenModal" :text="'+ Добавить кабинет'" />
			</div>

			<div v-if="tokens.length === 0" class="empty-state">
				У вас пока нет подключённых кабинетов Wildberries.
			</div>

			<ul v-else class="tokens-list">
				<li v-for="token in tokens" :key="token.id" class="token-item">
					<div class="token-left">
						<div class="token-main">
							<span class="token-masked">{{ token.label || 'Wildberries' }}</span>
							<span class="token-label">
								{{ token.marketplace?.toUpperCase() }} · {{ token.token_type || 'token' }}
							</span>
							<span class="token-status" :class="{ expired: isTokenExpired(token) }">
								{{ isTokenExpired(token) ? 'Недоступен' : 'Активен' }}
							</span>
						</div>

						<div class="token-dates">
							<span>Добавлен: {{ DateTransform.formatDate(token.issued_at) }}</span>
							<span v-if="token.expires_at">До: {{ DateTransform.formatDate(token.expires_at) }}</span>
						</div>
					</div>

					<div class="token-actions">
						<button @click="deleteToken(token.id)" class="btn-icon delete-btn" title="Удалить подключение">
							<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"
								stroke="currentColor" width="16" height="16">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
									d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M9 7h6" />
							</svg>
						</button>
					</div>
				</li>
			</ul>
		</div>
	</div>

	<SelectTariffModal v-if="showTariffModal" :is-open="true" @close="showTariffModal = false" @payment="toPay" />

	<AddTokenModal v-if="showAddTokenModal" :is-open="true" @close="showAddTokenModal = false"
		@success="handleTokenAdded" />
</template>

<style scoped>
.dashboard-container {
	padding: 20px;
}

@media (max-width: 1023px) {
	.dashboard-container {
		grid-template-columns: 1fr;
		padding: 16px;
	}
}

.profile-card {
	display: flex;
	flex-direction: column;
	justify-content: space-between;
	width: 100%;
	padding: 24px;
	background-color: var(--card-bg);
	border: 1px solid var(--border-color);
	border-radius: 12px;
	box-shadow: var(--shadow);
	gap: 20px;
}

.profile-header {
	display: flex;
	justify-content: space-between;
	align-items: center;
}

.left {
	display: flex;
	align-items: center;
	gap: 16px;
}

.right {
	display: flex;
	flex-direction: column;
	align-items: flex-end;
	gap: 8px;
}

.tariff-badge {
	display: flex;
	align-items: center;
	gap: 10px;
	background: rgba(52, 152, 219, 0.1);
	padding: 6px 12px;
	border-radius: 20px;
	border: 1px solid rgba(52, 152, 219, 0.3);
}

.tariff-status.active {
	background: rgba(46, 204, 113, 0.2);
	color: #2ecc71;
}

.tariff-status.expired {
	background: rgba(231, 76, 60, 0.2);
	color: #e74c3c;
}

.tariff-status.cancelled {
	background: rgba(241, 196, 15, 0.2);
	color: #f1c40f;
}

.tariff-dates {
	font-size: 12px;
	color: #888;
	margin-top: 4px;
	text-align: right;
}

.profile-actions {
	display: flex;
	gap: 12px;
	flex-wrap: wrap;
}

.edit-btn,
.change-tariff-btn {
	display: inline-flex;
	align-items: center;
	gap: 8px;
	padding: 10px 16px;
	border: none;
	border-radius: 6px;
	font-weight: 500;
	cursor: pointer;
	transition: var(--transition);
}

.edit-btn {
	background-color: var(--secondary-color);
	color: white;
}

.edit-btn:hover {
	background-color: #2980b9;
	transform: translateY(-2px);
}

.change-tariff-btn {
	background-color: var(--info-color);
	color: white;
}

.change-tariff-btn:hover {
	background-color: #8e44ad;
	transform: translateY(-2px);
}

.tokens-section {
	background-color: var(--card-bg);
	border: 1px solid var(--border-color);
	border-radius: 12px;
	padding: 24px;
	box-shadow: var(--shadow);
	margin-top: 20px;
}

.section-header {
	display: flex;
	justify-content: space-between;
	align-items: center;
	margin-bottom: 16px;
}

.section-header h3 {
	font-size: 1.25rem;
	font-weight: 600;
	color: var(--text-color);
}

.account-grid {
	display: grid;
	grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
	gap: 16px;
	margin-top: 20px;
}

.account-card {
	background: var(--medium-bg);
	border: 1px solid var(--border-color);
	border-radius: 10px;
	padding: 16px;
	transition: 0.2s;
}

.account-card:hover {
	transform: translateY(-2px);
	box-shadow: 0 6px 20px rgba(0, 0, 0, 0.3);
}

.card-title {
	font-size: 12px;
	color: #888;
	margin-bottom: 6px;
	text-transform: uppercase;
}

.card-value {
	font-size: 16px;
	font-weight: 600;
	color: var(--text-color);
}

.add-token-btn {
	padding: 8px 16px;
	background-color: var(--success-color);
	color: white;
	border: none;
	border-radius: 6px;
	font-weight: 500;
	cursor: pointer;
	transition: var(--transition);
}

.add-token-btn:hover {
	background-color: #27ae60;
	transform: translateY(-1px);
}

.empty-state {
	color: #aaa;
	font-style: italic;
	text-align: center;
	padding: 20px;
}

.tokens-list {
	list-style: none;
	padding: 0;
	margin: 0;
}

.token-item {
	display: flex;
	justify-content: space-between;
	align-items: center;
	padding: 16px;
	background-color: var(--medium-bg);
	border-radius: 10px;
	margin-bottom: 12px;
	border: 1px solid var(--border-color);
	transition: var(--transition);
}

.token-item:hover {
	background-color: var(--hover-bg);
	transform: translateY(-2px);
	box-shadow: 0 6px 20px rgba(0, 0, 0, 0.3);
}

.token-left {
	display: flex;
	flex-direction: column;
	gap: 6px;
}

.token-status {
	font-size: 12px;
	padding: 2px 8px;
	border-radius: 6px;
	background: rgba(46, 204, 113, 0.2);
	color: #2ecc71;
}

.token-status.expired {
	background: rgba(231, 76, 60, 0.2);
	color: #e74c3c;
}

.token-main {
	display: flex;
	align-items: center;
	gap: 10px;
	flex-wrap: wrap;
}

.token-label {
	font-size: 12px;
	color: #888;
	text-transform: uppercase;
}

.token-masked {
	font-size: 14px;
	font-weight: 600;
	color: var(--text-color);
}

.token-dates {
	display: flex;
	gap: 15px;
	font-size: 12px;
	color: #777;
	flex-wrap: wrap;
}

.token-actions {
	display: flex;
	gap: 8px;
	margin-left: 16px;
}

.btn-icon {
	width: 32px;
	height: 32px;
	border-radius: 6px;
	background-color: var(--light-bg);
	border: 1px solid var(--border-color);
	display: flex;
	align-items: center;
	justify-content: center;
	cursor: pointer;
	transition: var(--transition);
}

.btn-icon:hover {
	background-color: var(--hover-bg);
}

.delete-btn:hover {
	background-color: var(--accent-color);
}

@media (max-width: 1023px) {
	.profile-actions {
		flex-direction: column;
	}

	.edit-btn,
	.change-tariff-btn {
		width: 100%;
		justify-content: center;
	}

	.section-header {
		flex-direction: column;
		align-items: flex-start;
		gap: 12px;
	}

	.token-item {
		flex-direction: column;
		align-items: flex-start;
		gap: 10px;
	}

	.token-actions {
		align-self: flex-end;
	}
}
</style>