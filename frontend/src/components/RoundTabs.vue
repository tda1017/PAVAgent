<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  items: {
    type: Array,
    required: true,
  },
})

const emit = defineEmits(['round-change'])

const activeRound = ref('image')

const imageCount = computed(() => props.items.filter(i => i.type === 'image').length)
const sequenceCount = computed(() => props.items.filter(i => i.type === 'sequence').length)
const videoCount = computed(() => props.items.filter(i => i.type === 'video').length)

const tabs = computed(() => [
  { type: 'image', label: '单图测试', count: imageCount.value },
  { type: 'sequence', label: '连续帧序列', count: sequenceCount.value },
  { type: 'video', label: '视频理解', count: videoCount.value },
])

function select(tab) {
  if (tab.count === 0) return
  activeRound.value = tab.type
  emit('round-change', tab.type)
}
</script>

<template>
  <div class="tabs">
    <button
      v-for="tab in tabs"
      :key="tab.type"
      :class="['tab', { active: tab.type === activeRound, disabled: tab.count === 0 }]"
      @click="select(tab)"
    >
      {{ tab.label }} ({{ tab.count }})
    </button>
  </div>
</template>
