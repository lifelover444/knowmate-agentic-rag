<script setup lang="ts">
import { Message } from "@arco-design/web-vue";
import { computed } from "vue";
import { useRetrievalStore } from "../stores/retrieval";
import { formatApiError } from "../utils/api";

const retrieval = useRetrievalStore();

const profile = computed(() => retrieval.previewResult?.profile);
const protectedBlocks = computed(() => retrieval.previewResult?.protected_blocks);
const chunkDistribution = computed(() => retrieval.previewResult?.stats.size_distribution || {});

const chapterMarkerCount = computed(() => {
  const data = profile.value;
  if (!data) return 0;
  return data.german_chapter_count + data.english_chapter_count + data.chinese_chapter_count;
});

function rejectionTier(item: Record<string, unknown>) {
  return String(item.tier || "-");
}

function rejectionReason(item: Record<string, unknown>) {
  return String(item.reason || "未提供拒绝原因");
}

async function runPreview() {
  try {
    await retrieval.previewChunking();
    Message.success("切分预览已生成");
  } catch (error) {
    Message.error(`切分预览失败：${formatApiError(error instanceof Error ? error.message : error)}`);
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
        <a-descriptions-item label="策略链">{{ retrieval.previewResult.tier_chain.join(" -> ") }}</a-descriptions-item>
        <a-descriptions-item label="切片数">{{ retrieval.previewResult.stats.count }}</a-descriptions-item>
        <a-descriptions-item label="平均字符">{{ retrieval.previewResult.stats.avg_chars }}</a-descriptions-item>
        <a-descriptions-item label="最大字符">{{ retrieval.previewResult.stats.max_chars }}</a-descriptions-item>
        <a-descriptions-item label="平均 tokens">{{ retrieval.previewResult.stats.avg_tokens }}</a-descriptions-item>
        <a-descriptions-item label="最大 tokens">{{ retrieval.previewResult.stats.max_tokens }}</a-descriptions-item>
        <a-descriptions-item label="Token 上限">{{ retrieval.previewResult.stats.token_limit || "未设置" }}</a-descriptions-item>
        <a-descriptions-item label="生效 chunk size">{{ retrieval.previewResult.effective_chunk_size }}</a-descriptions-item>
        <a-descriptions-item label="标准差">{{ retrieval.previewResult.stats.stddev_chars }}</a-descriptions-item>
        <a-descriptions-item label="最小字符">{{ retrieval.previewResult.stats.min_chars }}</a-descriptions-item>
        <a-descriptions-item label="截断">{{ retrieval.previewResult.stats.truncated_to || "否" }}</a-descriptions-item>
      </a-descriptions>

      <a-alert
        v-if="retrieval.previewResult.token_limit_applied"
        type="info"
        :content="retrieval.previewResult.token_limit_reason"
      />

      <section class="debug-panel">
        <header>
          <h4>被拒绝层级</h4>
          <span>拒绝原因</span>
        </header>
        <a-empty v-if="!retrieval.previewResult.rejected.length" description="没有被拒绝的策略层级" />
        <div v-else class="debug-tags">
          <a-tag v-for="item in retrieval.previewResult.rejected" :key="rejectionTier(item)">
            {{ rejectionTier(item) }} · {{ rejectionReason(item) }}
          </a-tag>
        </div>
      </section>

      <section v-if="profile" class="debug-panel">
        <header>
          <h4>文档画像</h4>
          <span>只用于 preview/debug，不改变正式处理结果</span>
        </header>
        <div class="debug-grid">
          <div>
            <strong>{{ profile.md_heading_total }}</strong>
            <small>标题数</small>
          </div>
          <div>
            <strong>{{ profile.form_feed_count }}</strong>
            <small>分页符</small>
          </div>
          <div>
            <strong>{{ chapterMarkerCount }}</strong>
            <small>章节标记</small>
          </div>
          <div>
            <strong>{{ profile.has_tables ? "有表格" : "无表格" }} / {{ profile.has_code ? "有代码" : "无代码" }}</strong>
            <small>表格/代码</small>
          </div>
          <div>
            <strong>{{ profile.detected_langs.join(", ") || "-" }}</strong>
            <small>检测语言</small>
          </div>
          <div>
            <strong>{{ profile.total_lines }} / {{ profile.total_chars }}</strong>
            <small>行数 / 字符</small>
          </div>
        </div>
      </section>

      <section v-if="protectedBlocks" class="debug-panel">
        <header>
          <h4>保护块统计</h4>
          <span>公式、图片、链接、表格和代码块会尽量整体保留</span>
        </header>
        <div class="debug-tags">
          <a-tag>公式 {{ protectedBlocks.formula }}</a-tag>
          <a-tag>图片 {{ protectedBlocks.image }}</a-tag>
          <a-tag>链接 {{ protectedBlocks.markdown_link }}</a-tag>
          <a-tag>表格 {{ protectedBlocks.table }}</a-tag>
          <a-tag>代码 {{ protectedBlocks.code }}</a-tag>
          <a-tag color="blue">总计 {{ protectedBlocks.total }} · {{ protectedBlocks.total_chars }} 字</a-tag>
        </div>
      </section>

      <section class="debug-panel">
        <header>
          <h4>Chunk 分布</h4>
          <span>small / target / large</span>
        </header>
        <div class="debug-tags">
          <a-tag>small {{ chunkDistribution.small || 0 }}</a-tag>
          <a-tag color="green">target {{ chunkDistribution.target || 0 }}</a-tag>
          <a-tag color="orange">large {{ chunkDistribution.large || 0 }}</a-tag>
        </div>
      </section>

      <article v-for="chunk in retrieval.previewResult.chunks" :key="chunk.seq" class="preview-chunk">
        <strong>
          #{{ chunk.seq }} · {{ chunk.size_chars }} 字 · approx tokens {{ chunk.size_tokens_approx }}
        </strong>
        <small>start/end {{ chunk.start }}-{{ chunk.end }}</small>
        <small v-if="chunk.context_header">context_header {{ chunk.context_header }}</small>
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

.debug-panel {
  display: grid;
  gap: 10px;
  border: 1px solid var(--km-border);
  border-radius: 8px;
  padding: 12px;
  background: var(--km-surface);
}

.debug-panel header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}

.debug-panel h4 {
  margin: 0;
  font-size: 14px;
}

.debug-panel header span {
  color: var(--km-text-muted);
  font-size: 12px;
}

.debug-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 8px;
}

.debug-grid div {
  display: grid;
  gap: 3px;
  min-height: 58px;
  border: 1px solid var(--km-border);
  border-radius: 6px;
  padding: 8px;
  background: var(--km-bg);
}

.debug-grid strong {
  color: var(--km-text-primary);
  font-size: 14px;
  overflow-wrap: anywhere;
}

.debug-grid small {
  color: var(--km-text-muted);
}

.debug-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
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
