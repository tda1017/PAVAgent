<script setup>
import { computed } from 'vue'

const props = defineProps({
  metadata: {
    type: Object,
    required: true,
  },
})

const datePart = computed(() => {
  if (!props.metadata.generated_at) return ''
  return props.metadata.generated_at.split('T')[0]
})

const subtitle = computed(() => {
  const m = props.metadata
  return `${m.models.length} models · ${m.total_images} images · ${m.total_sequences} sequences · ${m.total_videos} videos · ${datePart.value}`
})
</script>

<template>
  <div class="card">
    <h1>PAVAgent · 视觉理解能力横向测评</h1>
    <p>{{ subtitle }}</p>
  </div>
</template>
