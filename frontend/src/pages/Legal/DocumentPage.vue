<script setup>
import { onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import LegalService from '@/API/LegalService'

const route = useRoute()
const documentData = ref(null)
const loading = ref(false)
const error = ref('')

const load = async () => {
	loading.value = true
	error.value = ''
	try {
		const response = await LegalService.document(String(route.params.code || ''))
		documentData.value = response.data?.document || null
	} catch (e) {
		documentData.value = null
		error.value = e?.response?.data?.error?.message || 'Документ не найден'
	} finally {
		loading.value = false
	}
}

watch(() => route.params.code, load)
onMounted(load)
</script>

<template>
	<main class="legal-page">
		<div class="legal-shell">
			<router-link to="/" class="back-link">← WB Insight</router-link>
			<p v-if="loading">Загрузка…</p>
			<div v-else-if="error" class="error">{{ error }}</div>
			<article v-else-if="documentData">
				<div class="legal-heading">
					<div>
						<h1>{{ documentData.title }}</h1>
						<p>Версия {{ documentData.version }}</p>
					</div>
					<span v-if="documentData.legal_review_required" class="draft">Черновик alpha</span>
				</div>
				<pre>{{ documentData.content }}</pre>
				<footer>SHA-256: {{ documentData.sha256 }}</footer>
			</article>
		</div>
	</main>
</template>

<style scoped>
.legal-page {
	min-height: 100vh;
	background: var(--dark-bg, #17191d);
	color: var(--text-color, #f1f1f1);
	padding: 40px 20px;
}
.legal-shell {
	max-width: 900px;
	margin: 0 auto;
}
.back-link {
	display: inline-block;
	margin-bottom: 24px;
}
.legal-heading {
	display: flex;
	justify-content: space-between;
	gap: 20px;
	align-items: flex-start;
	border-bottom: 1px solid var(--border-color, #333);
	padding-bottom: 18px;
	margin-bottom: 24px;
}
.legal-heading h1 {
	margin: 0 0 6px;
}
.legal-heading p {
	margin: 0;
	color: #999;
}
.draft {
	padding: 6px 10px;
	border: 1px solid #b7791f;
	border-radius: 999px;
	color: #d69e2e;
	white-space: nowrap;
}
pre {
	font: inherit;
	white-space: pre-wrap;
	word-break: break-word;
	line-height: 1.7;
	margin: 0;
}
footer {
	margin-top: 32px;
	padding-top: 16px;
	border-top: 1px solid var(--border-color, #333);
	color: #777;
	font-size: 12px;
	word-break: break-all;
}
.error {
	color: var(--danger-color, #d9534f);
}
</style>
