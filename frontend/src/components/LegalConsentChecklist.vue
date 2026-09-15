<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import LegalService from '@/API/LegalService'

const props = defineProps({
	context: { type: String, required: true },
	modelValue: { type: Array, default: () => [] }
})

const emit = defineEmits(['update:modelValue', 'valid'])
const documents = ref([])
const accepted = ref(new Set())
const loading = ref(false)
const error = ref('')

const isValid = computed(() => {
	return documents.value.length > 0 && documents.value.every((doc) => accepted.value.has(doc.code))
})

const publish = () => {
	const payload = documents.value
		.filter((doc) => accepted.value.has(doc.code))
		.map((doc) => ({
			code: doc.code,
			version: doc.version,
			sha256: doc.sha256,
			accepted: true
		}))
	emit('update:modelValue', payload)
	emit('valid', isValid.value)
}

const load = async () => {
	loading.value = true
	error.value = ''
	accepted.value = new Set()
	try {
		const response = await LegalService.requirements(props.context)
		documents.value = response.data?.documents || []
		publish()
	} catch (e) {
		documents.value = []
		error.value = e?.response?.data?.error?.message || 'Не удалось загрузить обязательные документы'
		publish()
	} finally {
		loading.value = false
	}
}

const toggle = (code, checked) => {
	const next = new Set(accepted.value)
	if (checked) next.add(code)
	else next.delete(code)
	accepted.value = next
	publish()
}

watch(() => props.context, load)
onMounted(load)
</script>

<template>
	<div class="legal-consents">
		<p v-if="loading" class="legal-status">Загружаем актуальные условия…</p>
		<p v-else-if="error" class="legal-error">{{ error }}</p>
		<label v-for="doc in documents" :key="`${doc.code}:${doc.version}`" class="legal-row">
			<input
				type="checkbox"
				:checked="accepted.has(doc.code)"
				@change="toggle(doc.code, $event.target.checked)"
			/>
			<span>
				Я принимаю
				<router-link :to="`/legal/${doc.code}`" target="_blank">{{ doc.title }}</router-link>
				<small>версия {{ doc.version }}</small>
				<small v-if="doc.legal_review_required" class="draft-badge">черновик для alpha</small>
			</span>
		</label>
	</div>
</template>

<style scoped>
.legal-consents {
	display: grid;
	gap: 10px;
	margin-top: 14px;
}
.legal-row {
	display: flex;
	gap: 10px;
	align-items: flex-start;
	line-height: 1.45;
}
.legal-row input {
	margin-top: 4px;
}
.legal-row small {
	display: block;
	color: #888;
	margin-top: 2px;
}
.draft-badge {
	color: #b7791f !important;
}
.legal-status {
	color: #888;
}
.legal-error {
	color: var(--danger-color, #d9534f);
}
</style>
