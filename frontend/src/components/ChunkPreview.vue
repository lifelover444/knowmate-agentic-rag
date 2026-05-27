<script setup lang="ts">
import { Message } from "@arco-design/web-vue";
import { useRetrievalStore } from "../stores/retrieval";
import { formatApiError } from "../utils/api";

const retrieval = useRetrievalStore();

async function runPreview() {
  try {
    await retrieval.previewChunking();
    Message.success("切分预览已生成");
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}
</script>

<template>
  <section class="chunk-preview">
    <a-textarea
      v-model="retrieval.previewSample"
      data-testid="preview-sample"
      :auto-size="{ minRows: 5, maxRows: 10 }"
      placeholder="输入一段用于预览的文档文本"
    />
    <div class="chunk-preview__actions">
      <a-button
        type="primary"
        data-testid="preview-chunking"
        :loading="retrieval.previewing"
        :disabled="!retrieval.previewSample.trim()"
        @click="runPreview"
      >
        切分预览
      </a-button>
    </div>
    <div v-if="retrieval.previewResult" class="preview-result" data-testid="preview-result">
      <a-descriptions :column="4" size="small" bordered>
        <a-descriptions-item label="命中策略">{{ retrieval.previewResult.selected_tier }}</a-descriptions-item>
        <a-descriptions-item label="切片数">{{ retrieval.previewResult.stats.count }}</a-descriptions-item>
        <a-descriptions-item label="平均字符">{{ retrieval.previewResult.stats.avg_chars }}</a-descriptions-item>
        <a-descriptions-item label="最大字符">{{ retrieval.previewResult.stats.max_chars }}</a-descriptions-item>
      </a-descriptions>
      <article v-for="chunk in retrieval.previewResult.chunks" :key="chunk.seq" class="preview-chunk">
        <strong>#{{ chunk.seq }} · {{ chunk.size_chars }} 字</strong>
        <small v-if="chunk.context_header">{{ chunk.context_header }}</small>
        <p>{{ chunk.content }}</p>
      </article>
    </div>
  </section>
</template>

<style scoped>
.chunk-preview {
  display: grid;
  gap: 14px;
}

.chunk-preview__actions {
  display: flex;
  justify-content: flex-end;
}

.preview-result {
  display: grid;
  gap: 12px;
}

.preview-chunk {
  display: grid;
  gap: 6px;
  border-top: 1px solid var(--km-border);
  padding-top: 12px;
}

.preview-chunk small {
  color: var(--km-primary-hover);
  white-space: pre-line;
}

.preview-chunk p {
  color: var(--km-text-primary);
  line-height: 1.65;
  white-space: pre-wrap;
}
</style>
