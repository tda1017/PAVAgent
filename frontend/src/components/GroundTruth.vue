<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  groundTruth: {
    type: Object,
    default: undefined,
  },
  currentResult: {
    type: Object,
    required: true,
  },
})

const expanded = ref(false)

const fields = computed(() => {
  if (!props.groundTruth) return []
  const gt = props.groundTruth
  const cr = props.currentResult
  return Object.keys(gt).map((key) => ({
    key,
    gt: gt[key],
    cr: cr[key],
    differ: cr[key] !== undefined && String(gt[key]) !== String(cr[key]),
  }))
})
</script>

<template>
  <div>
    <div class="collapse-header" @click="expanded = !expanded">
      {{ expanded ? '▾' : '▸' }} Ground Truth 对比
    </div>
    <div v-if="expanded">
      <p v-if="!groundTruth">暂无 Ground Truth 数据</p>
      <table v-else class="gt-table">
        <thead>
          <tr>
            <th>字段</th>
            <th>Ground Truth</th>
            <th>模型输出</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="f in fields" :key="f.key">
            <td>{{ f.key }}</td>
            <td>{{ f.gt }}</td>
            <td :class="{ differ: f.differ }">{{ f.cr }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
