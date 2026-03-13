<script setup>
import { ref } from 'vue'

const emit = defineEmits(['analyze-start'])
const dragOver = ref(false)
const previewUrl = ref(null)
const fileType = ref(null)
const uploading = ref(false)
const error = ref(null)

const ACCEPT = '.jpg,.jpeg,.png,.webp,.mp4,.mov,.avi'
const MAX_SIZE = 50 * 1024 * 1024

function onDragOver(e) {
  e.preventDefault()
  dragOver.value = true
}

function onDragLeave() {
  dragOver.value = false
}

function onDrop(e) {
  e.preventDefault()
  dragOver.value = false
  const file = e.dataTransfer?.files[0]
  if (file) handleFile(file)
}

function onFileSelect(e) {
  const file = e.target.files?.[0]
  if (file) handleFile(file)
}

async function handleFile(file) {
  error.value = null

  if (file.size > MAX_SIZE) {
    error.value = '文件过大，上限 50MB'
    return
  }

  // 本地预览
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
  previewUrl.value = URL.createObjectURL(file)
  fileType.value = file.type.startsWith('image/') ? 'image' : 'video'

  // 上传
  uploading.value = true
  try {
    const form = new FormData()
    form.append('file', file)
    const base = import.meta.env.BASE_URL.replace(/\/$/, '')
    const resp = await fetch(`${base}/api/analyze`, { method: 'POST', body: form })
    if (!resp.ok) {
      const body = await resp.json().catch(() => ({}))
      throw new Error(body.detail || `上传失败 (${resp.status})`)
    }
    const { task_id } = await resp.json()
    emit('analyze-start', { taskId: task_id, fileType: fileType.value })
  } catch (e) {
    error.value = e.message
  } finally {
    uploading.value = false
  }
}
</script>

<template>
  <div class="upload-panel">
    <!-- 预览区 -->
    <div v-if="previewUrl" class="preview-area">
      <img v-if="fileType === 'image'" :src="previewUrl" alt="预览" />
      <video v-else :src="previewUrl" controls />
    </div>

    <!-- 拖拽上传区 -->
    <div
      class="drop-zone"
      :class="{ active: dragOver, compact: previewUrl }"
      @dragover="onDragOver"
      @dragleave="onDragLeave"
      @drop="onDrop"
      @click="$refs.fileInput.click()"
    >
      <input
        ref="fileInput"
        type="file"
        :accept="ACCEPT"
        hidden
        @change="onFileSelect"
      />
      <template v-if="!previewUrl">
        <div class="drop-icon">+</div>
        <p class="drop-text">拖拽文件到这里，或点击选择</p>
        <p class="drop-hint">支持 jpg / png / webp / mp4 / mov，最大 50MB</p>
      </template>
      <template v-else>
        <span class="drop-text-compact">重新选择文件</span>
      </template>
    </div>

    <div v-if="uploading" class="upload-status">上传中...</div>
    <div v-if="error" class="error-box">{{ error }}</div>
  </div>
</template>

<style scoped>
.upload-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.preview-area {
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  overflow: hidden;
}

.preview-area img,
.preview-area video {
  max-width: 100%;
  max-height: 360px;
  object-fit: contain;
}

.drop-zone {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 24px;
  border: 2px dashed var(--border);
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
  background: var(--bg-card);
}

.drop-zone:hover,
.drop-zone.active {
  border-color: var(--accent);
  background: var(--bg-hover);
}

.drop-zone.compact {
  padding: 14px 24px;
}

.drop-icon {
  font-size: 36px;
  color: var(--text-muted);
  line-height: 1;
  margin-bottom: 12px;
}

.drop-text {
  font-size: 15px;
  color: var(--text-secondary);
}

.drop-text-compact {
  font-size: 14px;
  color: var(--text-muted);
}

.drop-hint {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 6px;
}

.upload-status {
  text-align: center;
  font-size: 14px;
  color: var(--text-muted);
}
</style>
