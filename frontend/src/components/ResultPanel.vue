<script setup>
import ScoreBadge from './ScoreBadge.vue'

defineProps({
  result: {
    type: Object,
    required: true,
  },
})
</script>

<template>
  <div class="card">
    <div v-if="result._error" class="error-box">
      {{ result._error }}
    </div>
    <template v-else>
      <div class="top-row">
        <ScoreBadge :score="result.importance_score" />
        <span v-if="result.category" class="label-tag">{{ result.category }}</span>
        <span v-if="result._latency_s != null" class="latency">⏱ {{ result._latency_s }}s</span>
      </div>

      <p v-if="result.summary" class="summary">{{ result.summary }}</p>

      <p v-if="result.reason" class="reason">
        <span class="reason-label">reason:</span> {{ result.reason }}
      </p>

      <div v-if="result.transition_detected" class="transition-info">
        <strong>Transition:</strong> {{ result.transition_type }}
        <span v-if="result.before_state"> | before: {{ result.before_state }}</span>
        <span v-if="result.after_state"> | after: {{ result.after_state }}</span>
      </div>

      <ul v-if="result.events && result.events.length" class="events-list">
        <li v-for="(evt, i) in result.events" :key="i">
          <span class="event-ts">{{ evt.timestamp_sec }}s</span> {{ evt.description }}
        </li>
      </ul>

      <p v-if="result.key_moment" class="key-moment">
        <strong>Key Moment:</strong> {{ result.key_moment }}
      </p>
    </template>
  </div>
</template>
