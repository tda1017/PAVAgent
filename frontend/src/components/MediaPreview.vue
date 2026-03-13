<script setup>
defineProps({
  fileType: String,
  previewUrl: String,
})
</script>

<template>
  <div class="media-preview">
    <img v-if="fileType === 'image'" :src="previewUrl" alt="上传预览" />
    <video v-else-if="fileType === 'video'" :src="previewUrl" controls />
  </div>
</template>

<style scoped>
.media-preview {
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  overflow: hidden;
}

.media-preview img,
.media-preview video {
  max-width: 100%;
  max-height: 400px;
  object-fit: contain;
}
</style>
