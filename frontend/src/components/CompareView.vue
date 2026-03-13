<script setup>
import { reactive, ref, computed } from 'vue'
import UploadPanel from './UploadPanel.vue'
import ModelCard from './ModelCard.vue'

const MODEL_ORDER = [
  'sonnet', 'kimi', 'gemini', 'gemini_flash_image', 'qwen', 'qwen_omni', 'gpt',
]

const modelStates = reactive({})
const activeModel = ref(null)
const analyzing = ref(false)
let currentES = null

const hasResults = computed(() => Object.keys(modelStates).length > 0)

const activeState = computed(() => {
  if (!activeModel.value) return null
  return modelStates[activeModel.value] || { status: 'pending' }
})

function initStates() {
  for (const name of MODEL_ORDER) {
    modelStates[name] = { status: 'pending' }
  }
  activeModel.value = MODEL_ORDER[0]
}

function statusIcon(status) {
  if (status === 'running') return '\u23F3'
  if (status === 'done') return '\u2705'
  if (status === 'error') return '\u274C'
  if (status === 'skipped') return '\u23ED'
  return '\u23F1'
}

function onAnalyzeStart({ taskId }) {
  if (currentES) {
    currentES.close()
    currentES = null
  }

  initStates()
  analyzing.value = true

  const base = import.meta.env.BASE_URL.replace(/\/$/, '')
  const es = new EventSource(`${base}/api/analyze/${taskId}/stream`)
  currentES = es

  es.onmessage = (event) => {
    const data = JSON.parse(event.data)

    if (data.status === 'complete') {
      analyzing.value = false
      es.close()
      currentES = null
      return
    }

    if (data.model) {
      modelStates[data.model] = data
      // 自动切换到第一个完成的模型
      if (data.status === 'done' && activeState.value?.status !== 'done') {
        activeModel.value = data.model
      }
    }
  }

  es.onerror = () => {
    analyzing.value = false
    es.close()
    currentES = null
  }
}
</script>

<template>
  <div class="compare-view">
    <UploadPanel @analyze-start="onAnalyzeStart" />

    <template v-if="hasResults">
      <!-- Tab 栏 -->
      <div class="model-tabs">
        <button
          v-for="name in MODEL_ORDER"
          :key="name"
          class="model-tab"
          :class="{
            active: activeModel === name,
            done: modelStates[name]?.status === 'done',
            running: modelStates[name]?.status === 'running',
            error: modelStates[name]?.status === 'error',
            skipped: modelStates[name]?.status === 'skipped',
          }"
          @click="activeModel = name"
        >
          <span class="tab-icon">{{ statusIcon(modelStates[name]?.status) }}</span>
          <span class="tab-name">{{ name }}</span>
        </button>
      </div>

      <!-- 内容区 -->
      <div class="model-content card">
        <ModelCard
          v-if="activeModel && activeState"
          :model-id="activeModel"
          :state="activeState"
        />
      </div>
    </template>
  </div>
</template>

<style scoped>
.compare-view {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.model-tabs {
  display: flex;
  gap: 0;
  overflow-x: auto;
  border-bottom: 1px solid var(--border);
}

.model-tab {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 10px 18px;
  border: none;
  border-bottom: 2px solid transparent;
  background: none;
  color: var(--text-muted);
  font-size: 14px;
  font-family: inherit;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.2s ease;
}

.model-tab:hover {
  color: var(--text);
  background: var(--bg-hover);
}

.model-tab.active {
  color: var(--text);
  border-bottom-color: var(--accent);
  font-weight: 600;
}

.model-tab.done .tab-icon { opacity: 1; }
.model-tab.running .tab-icon { animation: pulse 1s infinite; }
.model-tab.error { color: var(--error-text); }
.model-tab.error.active { border-bottom-color: var(--error-text); }
.model-tab.skipped { opacity: 0.5; }

.tab-icon {
  font-size: 12px;
}

.tab-name {
  font-size: 13px;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.model-content {
  min-height: 120px;
}
</style>
