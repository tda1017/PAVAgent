<script setup>
defineProps({
  models: {
    type: Array,
    required: true,
  },
  currentModel: {
    type: String,
    required: true,
  },
})

const emit = defineEmits(['model-change'])

function select(id) {
  emit('model-change', id)
}
</script>

<template>
  <div class="tabs">
    <button
      v-for="model in models"
      :key="model.id"
      :class="['tab', { active: model.id === currentModel }]"
      @click="select(model.id)"
    >
      {{ model.name }}
    </button>
  </div>
</template>
