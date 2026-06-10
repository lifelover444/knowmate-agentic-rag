<script setup lang="ts">
import type { SourceRead } from "../types/api";

defineProps<{
  source: SourceRead;
}>();

function score(value?: number | null): string {
  return typeof value === "number" ? value.toFixed(4) : "-";
}

function metadataText(metadata?: Record<string, unknown> | null): string {
  if (!metadata || Object.keys(metadata).length === 0) return "";
  return JSON.stringify(metadata, null, 2);
}

function sourceTitle(source: SourceRead): string {
  return source.document_title || source.title || source.document_id;
}

function retrievalMethodText(value?: string | null): string {
  const labels: Record<string, string> = {
    vector: "向量",
    keyword: "关键词",
    hybrid: "混合",
  };
  return labels[value || ""] || value || "未知";
}
</script>

<template>
  <article class="source-card">
    <header class="source-card__header">
      <div>
        <strong>{{ sourceTitle(source) }}</strong>
        <small v-if="source.knowledge_base_name">真实来源：{{ source.knowledge_base_name }}</small>
        <small>{{ source.document_id }} / {{ source.chunk_id }}</small>
      </div>
      <a-tag color="green">{{ retrievalMethodText(source.retrieval_method) }}</a-tag>
    </header>
    <div class="source-card__scores">
      <span>score {{ score(source.score) }}</span>
      <span v-if="source.vector_score !== null && source.vector_score !== undefined">vector_score {{ score(source.vector_score) }}</span>
      <span v-if="source.keyword_score !== null && source.keyword_score !== undefined">keyword_score {{ score(source.keyword_score) }}</span>
      <span v-if="source.rrf_score !== null && source.rrf_score !== undefined">rrf_score {{ score(source.rrf_score) }}</span>
      <span v-if="source.rerank_score !== null && source.rerank_score !== undefined">rerank_score {{ score(source.rerank_score) }}</span>
    </div>
    <div class="source-card__meta">
      <span v-if="source.source_type">source_type: {{ source.source_type }}</span>
      <span v-if="source.context_chunk_id">context_chunk_id: {{ source.context_chunk_id }}</span>
      <span v-if="source.parent_chunk_id">parent_chunk_id: {{ source.parent_chunk_id }}</span>
      <span v-if="source.chunk_type">chunk_type: {{ source.chunk_type }}</span>
      <span v-if="source.context_header">context_header: {{ source.context_header }}</span>
    </div>
    <p>{{ source.snippet || source.content }}</p>
    <details v-if="source.content && source.snippet && source.content !== source.snippet" class="source-card__detail">
      <summary>匹配 child 内容</summary>
      <p>{{ source.content }}</p>
    </details>
    <pre v-if="metadataText(source.metadata)" class="source-card__metadata">metadata 摘要
{{ metadataText(source.metadata) }}</pre>
  </article>
</template>

<style scoped>
.source-card {
  display: grid;
  gap: 10px;
  border: 1px solid var(--km-border);
  border-radius: var(--km-radius);
  padding: 14px;
  background: var(--km-bg-card);
}

.source-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.source-card__header div {
  display: grid;
  min-width: 0;
  gap: 4px;
}

.source-card strong {
  color: var(--km-text-primary);
}

.source-card small,
.source-card__scores,
.source-card__meta {
  color: var(--km-text-secondary);
  font-size: 12px;
}

.source-card__scores,
.source-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
}

.source-card p {
  color: var(--km-text-primary);
  line-height: 1.7;
  white-space: pre-wrap;
}

.source-card__metadata {
  overflow: auto;
  max-height: 180px;
  margin: 0;
  border-radius: var(--km-radius);
  padding: 10px;
  color: var(--km-text-secondary);
  background: var(--km-bg-page);
}

.source-card__detail {
  color: var(--km-text-secondary);
  font-size: 12px;
}

.source-card__detail p {
  margin: 8px 0 0;
  color: var(--km-text-secondary);
}
</style>
