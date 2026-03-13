<script setup>
import { ref, computed } from 'vue'
import report from './data/report.json'
import AppHeader from './components/AppHeader.vue'
import RoundTabs from './components/RoundTabs.vue'
import MediaBrowser from './components/MediaBrowser.vue'
import ModelTabs from './components/ModelTabs.vue'
import ResultPanel from './components/ResultPanel.vue'
import GroundTruth from './components/GroundTruth.vue'
import StatsTable from './components/StatsTable.vue'
import ThemeToggle from './components/ThemeToggle.vue'
import CompareView from './components/CompareView.vue'

const mode = ref('compare')

const currentRound = ref('image')
const currentIndex = ref(0)
const currentModelId = ref(report.metadata.models[0].id)

const filteredItems = computed(() =>
  report.items.filter((item) => item.type === currentRound.value)
)

const currentItem = computed(() =>
  filteredItems.value[currentIndex.value] ?? null
)

const currentResult = computed(() =>
  currentItem.value?.results[currentModelId.value] ?? null
)

function onRoundChange(round) {
  currentRound.value = round
  currentIndex.value = 0
}

function onPrev() {
  if (currentIndex.value > 0) currentIndex.value--
}

function onNext() {
  if (currentIndex.value < filteredItems.value.length - 1) currentIndex.value++
}

function onModelChange(modelId) {
  currentModelId.value = modelId
}
</script>

<template>
  <ThemeToggle />
  <div class="container">
    <div class="mode-switch">
      <button class="tab" :class="{ active: mode === 'compare' }" @click="mode = 'compare'">
        上传对比
      </button>
      <button class="tab" :class="{ active: mode === 'report' }" @click="mode = 'report'">
        历史报告
      </button>
    </div>

    <div v-show="mode === 'report'">
      <AppHeader :metadata="report.metadata" />
      <RoundTabs :items="report.items" @round-change="onRoundChange" />

      <template v-if="currentItem">
        <MediaBrowser
          :currentItem="currentItem"
          :currentIndex="currentIndex"
          :totalCount="filteredItems.length"
          @prev="onPrev"
          @next="onNext"
        />

        <div class="card">
          <ModelTabs
            :models="report.metadata.models"
            :currentModel="currentModelId"
            @model-change="onModelChange"
          />
          <ResultPanel v-if="currentResult" :result="currentResult" />
          <div v-else class="empty-state">该模型暂无此项结果</div>
        </div>

        <GroundTruth
          :groundTruth="currentItem.ground_truth"
          :currentResult="currentResult"
        />
      </template>

      <div v-else class="empty-state card">当前轮次暂无测试数据</div>

      <StatsTable :stats="report.stats" :models="report.metadata.models" />
    </div>

    <div v-show="mode === 'compare'">
      <CompareView />
    </div>
  </div>
</template>

<style scoped>
.container > * + * {
  margin-top: 1.5rem;
}

.empty-state {
  text-align: center;
  padding: 2rem 1rem;
  color: var(--text-muted);
}

.mode-switch {
  display: flex;
  gap: 8px;
  margin-bottom: 4px;
}
</style>
