<script setup lang="ts">
import { ref } from "vue";

defineProps<{
  uploading: boolean;
  polling: boolean;
}>();

const emit = defineEmits<{
  upload: [files: File[]];
}>();

const selectedFiles = ref<File[]>([]);

function handleFileSelected(event: Event) {
  const input = event.target as HTMLInputElement;
  selectedFiles.value = Array.from(input.files || []);
}

function submitUpload() {
  if (selectedFiles.value.length) emit("upload", selectedFiles.value);
}
</script>

<template>
  <section class="document-upload">
    <label class="file-picker">
      <input
        class="native-file-input"
        data-testid="file-input"
        type="file"
        multiple
        accept=".txt,.md,.pdf,.docx,.csv,.json,.xlsx"
        :disabled="uploading || polling"
        @change="handleFileSelected"
      />
      <span class="file-picker-button" data-testid="choose-file">
        {{ selectedFiles.length ? `已选择 ${selectedFiles.length} 个文件` : "选择文件" }}
      </span>
    </label>
    <a-button
      type="primary"
      data-testid="upload-doc"
      :loading="uploading || polling"
      :disabled="!selectedFiles.length || uploading || polling"
      @click="submitUpload"
    >
      上传并解析
    </a-button>
  </section>
</template>

<style scoped>
.document-upload {
  display: grid;
  grid-template-columns: minmax(240px, 1fr) auto;
  gap: 12px;
  align-items: center;
}

@media (max-width: 720px) {
  .document-upload {
    grid-template-columns: 1fr;
  }
}
</style>
