<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import BaseButton from '@/components/UI/Buttons/BaseButton.vue'

const props = defineProps({
	modelValue: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue'])

const editor = ref(null)
const previewDevice = ref('desktop')
const insertPanel = ref('')
const linkForm = ref({ text: '', url: '', button: false })
const imageForm = ref({ url: '', alt: '' })

const previewDocument = computed(() => `<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
</head>
<body style="margin:0;padding:24px;background:#f5f6fb;font-family:Arial,sans-serif;color:#182033">
	<div style="max-width:640px;margin:auto;background:#fff;padding:32px;border-radius:16px;box-sizing:border-box">
		${props.modelValue || '<p style="color:#94a3b8">Начните оформлять письмо — предпросмотр появится здесь.</p>'}
	</div>
</body>
</html>`)

function syncFromEditor() {
	emit('update:modelValue', editor.value?.innerHTML || '')
}

function run(command, value = null) {
	editor.value?.focus()
	document.execCommand(command, false, value)
	syncFromEditor()
}

function block(tag) {
	run('formatBlock', tag)
}

function escapeHtml(value) {
	return String(value || '')
		.replaceAll('&', '&amp;')
		.replaceAll('<', '&lt;')
		.replaceAll('>', '&gt;')
		.replaceAll('"', '&quot;')
		.replaceAll("'", '&#039;')
}

function insertHtml(html) {
	editor.value?.focus()
	document.execCommand('insertHTML', false, html)
	syncFromEditor()
}

function addLink() {
	const text = linkForm.value.text.trim()
	const url = linkForm.value.url.trim()
	if (!text || !/^(https?:\/\/|mailto:)/i.test(url)) return
	const safeText = escapeHtml(text)
	const safeUrl = escapeHtml(url)
	const html = linkForm.value.button
		? `<p><a href="${safeUrl}" data-mail-button="1">${safeText}</a></p>`
		: `<a href="${safeUrl}">${safeText}</a>`
	insertHtml(html)
	linkForm.value = { text: '', url: '', button: false }
	insertPanel.value = ''
}

function addImage() {
	const url = imageForm.value.url.trim()
	if (!/^https:\/\//i.test(url)) return
	insertHtml(`<p><img src="${escapeHtml(url)}" alt="${escapeHtml(imageForm.value.alt)}"></p>`)
	imageForm.value = { url: '', alt: '' }
	insertPanel.value = ''
}

function pastePlain(event) {
	event.preventDefault()
	const text = event.clipboardData?.getData('text/plain') || ''
	document.execCommand('insertText', false, text)
	syncFromEditor()
}

watch(
	() => props.modelValue,
	async (value) => {
		await nextTick()
		if (editor.value && editor.value.innerHTML !== (value || '')) {
			editor.value.innerHTML = value || ''
		}
	},
	{ immediate: true },
)
</script>

<template>
	<div class="mail-composer">
		<div class="composer-toolbar" role="toolbar" aria-label="Форматирование письма">
			<button type="button" title="Заголовок" @click="block('h2')">H2</button>
			<button type="button" title="Подзаголовок" @click="block('h3')">H3</button>
			<button type="button" title="Обычный текст" @click="block('p')">¶</button>
			<span class="toolbar-separator" />
			<button type="button" title="Жирный" @click="run('bold')"><strong>B</strong></button>
			<button type="button" title="Курсив" @click="run('italic')"><em>I</em></button>
			<button type="button" title="Подчёркивание" @click="run('underline')"><u>U</u></button>
			<span class="toolbar-separator" />
			<button type="button" title="Маркированный список" @click="run('insertUnorderedList')">• список</button>
			<button type="button" title="Нумерованный список" @click="run('insertOrderedList')">1. список</button>
			<button type="button" title="Цитата" @click="block('blockquote')">❝</button>
			<button type="button" title="Разделитель" @click="insertHtml('<hr>')">—</button>
			<span class="toolbar-separator" />
			<button type="button" @click="insertPanel = insertPanel === 'link' ? '' : 'link'">Ссылка / кнопка</button>
			<button type="button" @click="insertPanel = insertPanel === 'image' ? '' : 'image'">Картинка</button>
			<button type="button" title="Отменить" @click="run('undo')">↶</button>
			<button type="button" title="Повторить" @click="run('redo')">↷</button>
		</div>

		<Transition name="cp-expand">
			<div v-if="insertPanel === 'link'" class="composer-insert-panel">
				<label>Текст<input v-model.trim="linkForm.text" type="text" placeholder="Перейти в WB Insight"></label>
				<label>URL<input v-model.trim="linkForm.url" type="url" placeholder="https://..."></label>
				<label class="composer-check"><input v-model="linkForm.button" type="checkbox"> Оформить как CTA-кнопку</label>
				<BaseButton variant="primary" size="small" text="Вставить" :disabled="!linkForm.text || !linkForm.url" @click="addLink" />
			</div>
		</Transition>

		<Transition name="cp-expand">
			<div v-if="insertPanel === 'image'" class="composer-insert-panel">
				<label>HTTPS URL изображения<input v-model.trim="imageForm.url" type="url" placeholder="https://cdn.example.com/banner.jpg"></label>
				<label>Alt-текст<input v-model.trim="imageForm.alt" type="text" placeholder="Описание изображения"></label>
				<BaseButton variant="primary" size="small" text="Вставить" :disabled="!imageForm.url" @click="addImage" />
			</div>
		</Transition>

		<div class="composer-workspace">
			<div class="composer-editor-column">
				<div class="composer-column-head">
					<strong>Редактор</strong>
					<span>Вставка из буфера очищается до текста; оформление добавляйте панелью.</span>
				</div>
				<div
					ref="editor"
					class="composer-editor"
					contenteditable="true"
					role="textbox"
					aria-multiline="true"
					data-placeholder="Напишите письмо. Начните с заголовка, добавьте текст, кнопку и изображение…"
					@input="syncFromEditor"
					@blur="syncFromEditor"
					@paste="pastePlain"
				/>
			</div>

			<div class="composer-preview-column">
				<div class="composer-column-head composer-preview-head">
					<div>
						<strong>Предпросмотр</strong>
						<span>Приближенно к тому, что увидит получатель.</span>
					</div>
					<div class="device-toggle">
						<button type="button" :class="{ active: previewDevice === 'desktop' }" @click="previewDevice = 'desktop'">Desktop</button>
						<button type="button" :class="{ active: previewDevice === 'mobile' }" @click="previewDevice = 'mobile'">Mobile</button>
					</div>
				</div>
				<div class="preview-shell">
					<iframe
						title="Предпросмотр письма"
						sandbox=""
						:class="{ 'is-mobile': previewDevice === 'mobile' }"
						:srcdoc="previewDocument"
					/>
				</div>
			</div>
		</div>
	</div>
</template>

<style scoped>
.mail-composer {
	display: grid;
	gap: 10px;
}
.composer-toolbar {
	display: flex;
	flex-wrap: wrap;
	gap: 6px;
	padding: 8px;
	border: 1px solid var(--border-color);
	border-radius: 11px;
	background: var(--light-bg);
}
.composer-toolbar button,
.device-toggle button {
	min-height: 32px;
	padding: 6px 9px;
	border: 1px solid transparent;
	border-radius: 7px;
	background: transparent;
	color: var(--text-color);
	font: inherit;
	font-size: 12px;
	cursor: pointer;
}
.composer-toolbar button:hover,
.device-toggle button:hover,
.device-toggle button.active {
	border-color: var(--border-color);
	background: var(--card-bg);
}
.toolbar-separator {
	width: 1px;
	align-self: stretch;
	margin: 3px 2px;
	background: var(--border-color);
}
.composer-insert-panel {
	display: grid;
	grid-template-columns: minmax(180px, .8fr) minmax(260px, 1.2fr) auto auto;
	align-items: end;
	gap: 10px;
	padding: 12px;
	border: 1px solid color-mix(in srgb, var(--secondary-color) 22%, var(--border-color));
	border-radius: 10px;
	background: color-mix(in srgb, var(--secondary-color) 6%, var(--card-bg));
}
.composer-insert-panel label {
	display: grid;
	gap: 5px;
	color: var(--text-muted);
	font-size: 12px;
}
.composer-insert-panel input {
	width: 100%;
	min-height: 36px;
	box-sizing: border-box;
	padding: 8px 10px;
	border: 1px solid var(--border-color);
	border-radius: 8px;
	background: var(--card-bg);
	color: var(--text-color);
}
.composer-insert-panel .composer-check {
	display: flex;
	align-items: center;
	gap: 7px;
	padding-bottom: 8px;
	white-space: nowrap;
}
.composer-insert-panel .composer-check input {
	width: auto;
	min-height: 0;
}
.composer-workspace {
	display: grid;
	grid-template-columns: minmax(0, 1fr) minmax(360px, .9fr);
	gap: 12px;
}
.composer-editor-column,
.composer-preview-column {
	min-width: 0;
	border: 1px solid var(--border-color);
	border-radius: 12px;
	overflow: hidden;
	background: var(--card-bg);
}
.composer-column-head {
	min-height: 54px;
	padding: 10px 12px;
	display: flex;
	flex-direction: column;
	justify-content: center;
	gap: 2px;
	border-bottom: 1px solid var(--border-color);
}
.composer-column-head strong { font-size: 13px; }
.composer-column-head span { color: var(--text-subtle); font-size: 11px; }
.composer-preview-head {
	flex-direction: row;
	align-items: center;
	justify-content: space-between;
	gap: 12px;
}
.composer-preview-head > div:first-child {
	display: grid;
	gap: 2px;
}
.composer-editor {
	min-height: 420px;
	max-height: 620px;
	overflow: auto;
	padding: 24px;
	outline: 0;
	color: var(--text-color);
	line-height: 1.65;
}
.composer-editor:empty::before {
	content: attr(data-placeholder);
	color: var(--text-subtle);
	pointer-events: none;
}
.composer-editor :deep(img) {
	max-width: 100%;
	height: auto;
}
.device-toggle {
	display: flex;
	padding: 3px;
	border: 1px solid var(--border-color);
	border-radius: 8px;
	background: var(--light-bg);
}
.device-toggle button {
	min-height: 28px;
	padding: 4px 7px;
	font-size: 10px;
}
.preview-shell {
	min-height: 420px;
	padding: 14px;
	display: flex;
	justify-content: center;
	background: #e9ecf4;
	overflow: auto;
}
.preview-shell iframe {
	width: 100%;
	height: 560px;
	border: 0;
	border-radius: 8px;
	background: white;
	transition: width 260ms ease;
}
.preview-shell iframe.is-mobile {
	width: 390px;
	max-width: 100%;
}
@media (max-width: 1100px) {
	.composer-workspace { grid-template-columns: 1fr; }
}
@media (max-width: 760px) {
	.composer-insert-panel { grid-template-columns: 1fr; }
	.composer-insert-panel .composer-check { padding-bottom: 0; }
	.composer-editor { min-height: 320px; padding: 18px; }
}
</style>
