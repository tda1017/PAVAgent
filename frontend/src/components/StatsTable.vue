<script setup>
import { computed } from 'vue'

const props = defineProps({
  stats: {
    type: Object,
    required: true,
  },
  models: {
    type: Array,
    required: true,
  },
})

const ids = computed(() => props.models.map((m) => m.id))

const nameOf = (id) => {
  const m = props.models.find((m) => m.id === id)
  return m ? m.name : id
}

const fmt = (v, pct) => {
  if (v == null) return '-'
  return pct ? (v * 100).toFixed(1) + '%' : v
}

const fmtLatency = (v) => (v == null ? '-' : v.toFixed(1) + 's')

const best = computed(() => {
  const s = props.stats
  const all = ids.value
  const max = (fn) => all.reduce((best, id) => {
    const v = fn(s[id])
    return v != null && (best == null || v > fn(s[best])) ? id : best
  }, null)
  const min = (fn) => all.reduce((best, id) => {
    const v = fn(s[id])
    return v != null && (best == null || v < fn(s[best])) ? id : best
  }, null)

  return {
    accuracy: max((r) => r.category_accuracy),
    score_diff: min((r) => r.avg_score_diff),
    precision: max((r) => r.precision),
    recall: max((r) => r.recall),
    latency: min((r) => r.avg_latency_s),
  }
})
</script>

<template>
  <div class="card">
    <h3>汇总统计</h3>
    <table class="stats-table">
      <thead>
        <tr>
          <th>Model</th>
          <th>准确率</th>
          <th>Score偏差</th>
          <th>Precision</th>
          <th>Recall</th>
          <th>延迟</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="id in ids" :key="id">
          <td>{{ nameOf(id) }}</td>
          <td :class="{ best: best.accuracy === id }">
            {{ fmt(stats[id].category_accuracy, true) }}
          </td>
          <td :class="{ best: best.score_diff === id }">
            {{ stats[id].avg_score_diff ?? '-' }}
          </td>
          <td :class="{ best: best.precision === id }">
            {{ fmt(stats[id].precision, true) }}
          </td>
          <td :class="{ best: best.recall === id }">
            {{ fmt(stats[id].recall, true) }}
          </td>
          <td :class="{ best: best.latency === id }">
            {{ fmtLatency(stats[id].avg_latency_s) }}
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
