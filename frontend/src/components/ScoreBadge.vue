<script setup>
import { computed } from 'vue'

const props = defineProps({
  score: {
    type: Number,
    required: true,
  },
})

const colorClass = computed(() => {
  if (props.score <= 3) return 'score-green'
  if (props.score <= 6) return 'score-yellow'
  return 'score-red'
})
</script>

<template>
  <span class="score-badge" :class="colorClass">{{ score }}/10</span>
</template>
