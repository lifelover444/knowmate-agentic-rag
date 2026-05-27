<script setup lang="ts">
import { ref } from "vue";

defineProps<{
  uploading: boolean;
  polling: boolean;
}>();

const emit = defineEmits<{
  upload: [file: File];
}>();

const selectedFile = ref<File | null>(null);

function handleFileSelected(event: Event) {
  const input = event.target as HTMLInputElement;
  selectedFile.value = input.files?.[0] || null;
}

function submitUpload() {
  if (selectedFile.value) emit("upload", selectedFile.value);
}
</script>

<template>
  <section class="document-upload">
    <label class="file-picker">
      <input
        class="native-file-input"
        data-testid="file-input"
        type="file"
        accept=".txt,.md,.pdf,.docx,.csv,.json,.xlsx"
        :disabled="uploading || polling"
        @change="handleFileSelected"
      />
      <span class="file-picker-button" data-testid="choose-file">
        {{ selectedFile?.name || "选择文件" }}
      </span>
    </label>
    <a-button
      type="primary"
      data-testid="upload-doc"
      :loading="uploading || polling"
      :disabled="!selectedFile || uploading || polling"
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
