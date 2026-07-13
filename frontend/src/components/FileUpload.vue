<template>
  <div class="file-upload">
    <div
      class="upload-dropzone"
      :class="{ dragging, success: uploadResult?.status === 'ok', error: uploadError }"
      @dragover.prevent="dragging = true"
      @dragleave.prevent="dragging = false"
      @drop.prevent="handleDrop"
      @click="triggerFileInput"
    >
      <input
        ref="fileInputRef"
        type="file"
        accept=".csv,.xlsx,.xls"
        class="file-input-hidden"
        @change="handleFileSelect"
      />

      <template v-if="!uploading">
        <svg class="upload-icon" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
          <polyline points="17 8 12 3 7 8"/>
          <line x1="12" y1="3" x2="12" y2="15"/>
        </svg>
        <p class="upload-text">拖拽文件到此处，或点击选择</p>
        <p class="upload-hint">支持 CSV、Excel (.xlsx/.xls)，最大 {{ maxSizeMB }}MB</p>
      </template>

      <template v-else>
        <div class="upload-progress">
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: progress + '%' }"></div>
          </div>
          <span class="progress-text">{{ progress }}%</span>
        </div>
      </template>
    </div>

    <div v-if="uploadResult?.status === 'ok'" class="upload-result success">
      <span class="result-icon">&#10003;</span>
      <div class="result-info">
        <strong>已导入表 [{{ uploadResult.table_name }}]</strong>
        <span>{{ uploadResult.row_count }} 行 {{ uploadResult.columns?.length || 0 }} 列</span>
        <span v-if="uploadResult.chunks_added">向量索引已更新 ({{ uploadResult.chunks_added }} 块)</span>
      </div>
    </div>

    <div v-if="uploadError" class="upload-result error">
      <span class="result-icon">&#10007;</span>
      <span>{{ uploadError }}</span>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { uploadFile } from '../api'

const props = defineProps({
  maxSizeMB: { type: Number, default: 50 },
})

const fileInputRef = ref(null)
const dragging = ref(false)
const uploading = ref(false)
const progress = ref(0)
const uploadResult = ref(null)
const uploadError = ref('')

function triggerFileInput() {
  if (!uploading.value) {
    fileInputRef.value?.click()
  }
}

function handleDrop(e) {
  dragging.value = false
  const file = e.dataTransfer?.files?.[0]
  if (file) processFile(file)
}

function handleFileSelect(e) {
  const file = e.target?.files?.[0]
  if (file) processFile(file)
  if (fileInputRef.value) fileInputRef.value.value = ''
}

async function processFile(file) {
  uploadError.value = ''
  uploadResult.value = null

  const ext = file.name.split('.').pop()?.toLowerCase()
  if (!['csv', 'xlsx', 'xls'].includes(ext)) {
    uploadError.value = `不支持的文件类型 .${ext}，仅支持 csv、xlsx、xls`
    return
  }
  if (file.size > props.maxSizeMB * 1024 * 1024) {
    uploadError.value = `文件大小超过限制（最大 ${props.maxSizeMB}MB）`
    return
  }

  uploading.value = true
  progress.value = 0

  try {
    const { data } = await uploadFile(file, null, {
      onUploadProgress: (e) => {
        if (e.total) {
          progress.value = Math.round((e.loaded / e.total) * 100)
        }
      },
    })
    uploadResult.value = data
    progress.value = 100
  } catch (err) {
    const detail = err.response?.data?.detail || err.message
    uploadError.value = typeof detail === 'string' ? detail : '上传失败，请重试'
  } finally {
    uploading.value = false
  }
}
</script>

<style scoped>
.file-upload {
  margin: 8px 0;
}

.upload-dropzone {
  border: 2px dashed rgba(255, 255, 255, 0.2);
  border-radius: var(--radius-sm);
  padding: 16px 12px;
  text-align: center;
  cursor: pointer;
  transition: all var(--transition);
  position: relative;
}

.upload-dropzone:hover {
  border-color: var(--primary);
  background: rgba(79, 70, 229, 0.08);
}

.upload-dropzone.dragging {
  border-color: var(--primary);
  background: rgba(79, 70, 229, 0.15);
}

.upload-dropzone.success {
  border-color: var(--success);
  background: rgba(16, 185, 129, 0.08);
}

.upload-dropzone.error {
  border-color: var(--danger);
  background: rgba(239, 68, 68, 0.08);
}

.file-input-hidden {
  display: none;
}

.upload-icon {
  color: #64748b;
  margin-bottom: 6px;
}

.upload-text {
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 2px;
}

.upload-hint {
  font-size: 10px;
  color: #64748b;
}

.upload-progress {
  padding: 8px 0;
}

.progress-bar {
  height: 4px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 2px;
  overflow: hidden;
  margin-bottom: 6px;
}

.progress-fill {
  height: 100%;
  background: var(--primary);
  border-radius: 2px;
  transition: width 0.3s ease;
}

.progress-text {
  font-size: 11px;
  color: #94a3b8;
}

.upload-result {
  margin-top: 8px;
  padding: 8px 10px;
  border-radius: 6px;
  font-size: 12px;
  display: flex;
  align-items: flex-start;
  gap: 6px;
}

.upload-result.success {
  background: rgba(16, 185, 129, 0.12);
  color: #6ee7b7;
}

.upload-result.error {
  background: rgba(239, 68, 68, 0.12);
  color: #fca5a5;
}

.result-icon {
  font-size: 14px;
  flex-shrink: 0;
  margin-top: 1px;
}

.result-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
</style>