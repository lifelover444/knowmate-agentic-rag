<script setup lang="ts">
import { Message } from "@arco-design/web-vue";
import { onMounted } from "vue";
import ChunkPreview from "../components/ChunkPreview.vue";
import { useModelsStore } from "../stores/models";
import { useRetrievalStore } from "../stores/retrieval";
import { formatApiError } from "../utils/api";

const retrieval = useRetrievalStore();
const modelStore = useModelsStore();

async function saveConfig() {
  try {
    await retrieval.saveRetrievalConfig();
    Message.success("检索配置已保存");
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

onMounted(() => {
  Promise.all([
    retrieval.loadRetrievalConfig(),
    retrieval.loadParserEngines(),
    modelStore.loadModels(),
  ]).catch((error) => {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  });
});
</script>

<template>
  <main class="page-shell">
    <a-page-header title="检索配置" subtitle="控制 quick-answer 的召回、RRF、Rerank 和解析切分默认参数。" />
    <section class="content-card">
      <a-tabs default-active-key="retrieval">
        <a-tab-pane key="retrieval" title="检索参数">
          <div class="form-grid">
            <a-form-item label="retrieval mode">
              <a-select v-model="retrieval.retrievalMode" data-testid="retrieval-mode">
                <a-option value="hybrid">Hybrid：向量 + 关键词</a-option>
                <a-option value="vector_only">仅向量</a-option>
                <a-option value="keyword_only">仅关键词</a-option>
              </a-select>
            </a-form-item>
            <a-form-item label="embedding topK">
              <a-input-number v-model="retrieval.retrievalEmbeddingTopK" data-testid="retrieval-embedding-top-k" :min="1" :max="500" />
            </a-form-item>
            <a-form-item label="vector threshold">
              <a-input-number v-model="retrieval.retrievalVectorThreshold" data-testid="retrieval-vector-threshold" :min="0" :max="1" :step="0.01" />
            </a-form-item>
            <a-form-item label="keyword threshold">
              <a-input-number v-model="retrieval.retrievalKeywordThreshold" data-testid="retrieval-keyword-threshold" :min="0" :max="1" :step="0.01" />
            </a-form-item>
            <a-form-item label="RRF K">
              <a-input-number v-model="retrieval.retrievalRrfK" data-testid="retrieval-rrf-k" :min="1" :max="500" />
            </a-form-item>
            <a-form-item label="vector weight">
              <a-input-number v-model="retrieval.retrievalRrfVectorWeight" data-testid="retrieval-rrf-vector-weight" :min="0.1" :max="10" :step="0.1" />
            </a-form-item>
            <a-form-item label="keyword weight">
              <a-input-number v-model="retrieval.retrievalRrfKeywordWeight" data-testid="retrieval-rrf-keyword-weight" :min="0.1" :max="10" :step="0.1" />
            </a-form-item>
            <a-form-item label="enable rerank">
              <a-switch v-model="retrieval.retrievalEnableRerank" data-testid="retrieval-enable-rerank" />
            </a-form-item>
            <a-form-item label="rerank model">
              <a-select v-model="retrieval.selectedRerankModelId" data-testid="rerank-model-select" allow-clear>
                <a-option v-for="model in modelStore.rerankModels" :key="model.id" :value="model.id">
                  {{ model.name }} · {{ model.model_name }}
                </a-option>
              </a-select>
            </a-form-item>
            <a-form-item label="rerank topK">
              <a-input-number v-model="retrieval.retrievalRerankTopK" data-testid="retrieval-rerank-top-k" :min="1" :max="50" />
            </a-form-item>
            <a-form-item label="rerank threshold">
              <a-input-number v-model="retrieval.retrievalRerankThreshold" data-testid="retrieval-rerank-threshold" :min="-10" :max="10" :step="0.01" />
            </a-form-item>
          </div>
          <div class="actions-row">
            <a-button type="primary" data-testid="save-retrieval" :loading="retrieval.saving" @click="saveConfig">
              保存配置
            </a-button>
          </div>
        </a-tab-pane>

        <a-tab-pane key="chunking" title="切分配置">
          <div class="form-grid">
            <a-form-item label="PDF 解析引擎">
              <a-select v-model="retrieval.parserEngineRules[0].engine" data-testid="parser-pdf">
                <a-option v-for="engine in retrieval.parserEngines" :key="engine.name" :value="engine.name" :disabled="!engine.available">
                  {{ engine.name }}{{ engine.available ? "" : "（不可用）" }}
                </a-option>
              </a-select>
            </a-form-item>
            <a-form-item label="Office 解析引擎">
              <a-select v-model="retrieval.parserEngineRules[1].engine" data-testid="parser-office">
                <a-option v-for="engine in retrieval.parserEngines" :key="engine.name" :value="engine.name" :disabled="!engine.available">
                  {{ engine.name }}{{ engine.available ? "" : "（不可用）" }}
                </a-option>
              </a-select>
            </a-form-item>
            <a-form-item label="strategy">
              <a-select v-model="retrieval.chunkStrategy" data-testid="chunk-strategy">
                <a-option value="auto">自动：标题 → 启发式 → 传统递归</a-option>
                <a-option value="heading">标题优先</a-option>
                <a-option value="heuristic">启发式边界</a-option>
                <a-option value="legacy">传统递归</a-option>
              </a-select>
            </a-form-item>
            <a-form-item label="chunk size">
              <a-input-number v-model="retrieval.chunkSize" data-testid="chunk-size" :min="50" :max="10000" />
            </a-form-item>
            <a-form-item label="overlap">
              <a-input-number v-model="retrieval.chunkOverlap" data-testid="chunk-overlap" :min="0" :max="2000" />
            </a-form-item>
            <a-form-item label="separators">
              <a-input v-model="retrieval.separatorsText" data-testid="chunk-separators" />
            </a-form-item>
            <a-form-item label="token limit">
              <a-input-number v-model="retrieval.tokenLimit" data-testid="token-limit" :min="0" :max="8192" />
            </a-form-item>
            <a-form-item label="languages">
              <a-input v-model="retrieval.languagesText" data-testid="chunk-languages" placeholder="zh,en" />
            </a-form-item>
            <a-form-item label="Parent-Child">
              <a-switch v-model="retrieval.enableParentChild" data-testid="enable-parent-child" />
            </a-form-item>
            <a-form-item label="parent size">
              <a-input-number v-model="retrieval.parentChunkSize" data-testid="parent-chunk-size" :min="512" :max="8192" :disabled="!retrieval.enableParentChild" />
            </a-form-item>
            <a-form-item label="child size">
              <a-input-number v-model="retrieval.childChunkSize" data-testid="child-chunk-size" :min="64" :max="2048" :disabled="!retrieval.enableParentChild" />
            </a-form-item>
          </div>
          <ChunkPreview />
        </a-tab-pane>
      </a-tabs>
    </section>
  </main>
</template>
