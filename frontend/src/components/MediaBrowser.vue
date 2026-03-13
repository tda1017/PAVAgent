<template>
  <div class="media-browser">
    <div class="nav-area">
      <button
        class="nav-btn"
        :disabled="currentIndex === 0"
        @click="$emit('prev')"
      >
        &larr;
      </button>
      <span class="filename">{{ currentItem.filename }} ({{ currentIndex + 1 }} / {{ totalCount }})</span>
      <button
        class="nav-btn"
        :disabled="currentIndex === totalCount - 1"
        @click="$emit('next')"
      >
        &rarr;
      </button>
    </div>

    <div class="media-container">
      <template v-if="currentItem.type === 'image'">
        <img :src="currentItem.media_base64" class="media-image" />
      </template>

      <template v-else-if="currentItem.type === 'sequence'">
        <div class="sequence-preview">
          <img
            :src="currentItem.frames_base64[selectedFrame]"
            class="sequence-enlarged"
          />
        </div>
        <div class="sequence-thumbnails">
          <img
            v-for="(frame, i) in currentItem.frames_base64"
            :key="i"
            :src="frame"
            class="thumbnail"
            :class="{ active: i === selectedFrame }"
            @click="selectedFrame = i"
          />
        </div>
      </template>

      <template v-else-if="currentItem.type === 'video'">
        <video
          v-if="currentItem.media_base64"
          controls
          :src="currentItem.media_base64"
          class="media-video"
        />
        <div v-else class="video-placeholder">
          视频预览不可用（文件过大）
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  currentItem: {
    type: Object,
    required: true,
  },
  currentIndex: {
    type: Number,
    required: true,
  },
  totalCount: {
    type: Number,
    required: true,
  },
})

const emit = defineEmits(['prev', 'next'])

const selectedFrame = ref(0)

watch(
  () => props.currentItem.id,
  () => {
    selectedFrame.value = 0
  }
)

function onKeydown(e) {
  if (e.key === 'ArrowLeft' && props.currentIndex > 0) {
    emit('prev')
  } else if (e.key === 'ArrowRight' && props.currentIndex < props.totalCount - 1) {
    emit('next')
  }
}

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
})
</script>

<style scoped>
.media-browser {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.nav-area {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.nav-btn {
  padding: 6px 16px;
  font-size: 18px;
  cursor: pointer;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--bg-card);
}

.nav-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.filename {
  font-weight: 500;
  text-align: center;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding: 0 12px;
}

.media-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}

.media-image,
.sequence-enlarged,
.media-video {
  max-width: 100%;
  max-height: 520px;
  object-fit: contain;
  border-radius: 4px;
}

.sequence-preview {
  display: flex;
  justify-content: center;
}

.sequence-thumbnails {
  display: flex;
  gap: 6px;
  overflow-x: auto;
  padding: 4px 0;
}

.thumbnail {
  width: 72px;
  height: 54px;
  object-fit: cover;
  cursor: pointer;
  border: 2px solid transparent;
  border-radius: 3px;
  opacity: 0.7;
  transition: opacity 0.15s, border-color 0.15s;
}

.thumbnail:hover {
  opacity: 1;
}

.thumbnail.active {
  border-color: #409eff;
  opacity: 1;
}

.video-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  min-height: 200px;
  background: var(--bg-input);
  color: var(--text-muted);
  border-radius: 4px;
  font-size: 14px;
}
</style>
