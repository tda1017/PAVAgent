<script setup>
import ScoreBadge from './ScoreBadge.vue'

const props = defineProps({
  modelId: { type: String, required: true },
  state: { type: Object, required: true },
})
</script>

<template>
  <div class="model-card-inner">
    <!-- pending -->
    <div v-if="state.status === 'pending'" class="state-msg muted">
      等待中...
    </div>

    <!-- running -->
    <div v-else-if="state.status === 'running'" class="state-msg running">
      <span class="spinner-dot"></span> {{ state.progress ? `分析中 (${state.progress})...` : '分析中...' }}
    </div>

    <!-- skipped -->
    <div v-else-if="state.status === 'skipped'" class="state-msg muted">
      该模型不支持此文件类型
    </div>

    <!-- error -->
    <div v-else-if="state.status === 'error'" class="error-box">
      {{ state.error }}
    </div>

    <!-- done -->
    <div v-else-if="state.status === 'done' && state.result" class="result-body">
      <div v-if="state.result._error" class="error-box">{{ state.result._error }}</div>
      <template v-else>
        <div class="result-top">
          <ScoreBadge :score="state.result.importance_score" />
          <span v-if="state.result.category" class="label-tag">{{ state.result.category }}</span>
          <span v-if="state.result._latency_s != null" class="latency">{{ state.result._latency_s }}s</span>
        </div>
        <p v-if="state.result.summary" class="summary">{{ state.result.summary }}</p>
        <p v-if="state.result.reason" class="reason">
          <span class="reason-label">reason:</span> {{ state.result.reason }}
        </p>
        <ul v-if="state.result.events?.length" class="events-list">
          <li v-for="(evt, i) in state.result.events" :key="i">
            <span class="event-ts">{{ evt.timestamp_sec }}s</span> {{ evt.description }}
          </li>
        </ul>
        <p v-if="state.result.key_moment" class="key-moment">
          <strong>Key Moment:</strong> {{ state.result.key_moment }}
        </p>
      </template>
    </div>
  </div>
</template>

<style scoped>
.state-msg {
  font-size: 14px;
  padding: 12px 0;
}

.state-msg.muted {
  color: var(--text-muted);
}

.state-msg.running {
  color: #3b82f6;
  display: flex;
  align-items: center;
  gap: 8px;
}

.spinner-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #3b82f6;
  animation: pulse 1s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.result-top {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}

.summary {
  font-size: 15px;
  line-height: 1.7;
  margin-bottom: 10px;
}

.reason {
  font-size: 14px;
  color: var(--text-secondary);
  margin-bottom: 10px;
}

.reason-label {
  font-weight: 600;
}

.events-list {
  list-style: none;
  font-size: 14px;
  margin-bottom: 10px;
}

.events-list li {
  padding: 4px 0;
  line-height: 1.6;
}

.event-ts {
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  margin-right: 8px;
  color: var(--accent);
}

.key-moment {
  font-size: 14px;
  margin-top: 8px;
  line-height: 1.6;
}
</style>
