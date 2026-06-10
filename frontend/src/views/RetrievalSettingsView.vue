<script setup lang="ts">
import { Message } from "@arco-design/web-vue";
import { computed, onMounted } from "vue";
import ChunkPreview from "../components/ChunkPreview.vue";
import { useModelsStore } from "../stores/models";
import { useRetrievalStore } from "../stores/retrieval";
import { formatApiError } from "../utils/api";

const retrieval = useRetrievalStore();
const modelStore = useModelsStore();

const rerankStatusText = computed(() => (retrieval.selectedRerankModelId ? "已配置" : "未配置"));
const rerankStatusColor = computed(() => (retrieval.selectedRerankModelId ? "green" : "gold"));
const qdrantStatusText = computed(() => retrieval.runtimeStatus?.vector_store?.status || "unknown");
const paradeDbStatusText = computed(() => {
  const status = retrieval.runtimeStatus?.database?.status;
  return status === "ok" ? "随 PostgreSQL/ParadeDB 迁移检查" : "待检查";
});

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
    retrieval.loadRuntimeStatus(),
    modelStore.loadModels(),
  ]).catch((error) => {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  });
});
</script>

<template>
  <main class="page-shell">
    <a-page-header title="检索配置" subtitle="v0.9 固定主链路：Qdrant dense + ParadeDB BM25 + RRF + 必需 rerank + parent-child context。" />
    <section class="content-card">
      <a-tabs default-active-key="retrieval">
        <a-tab-pane key="retrieval" title="检索参数">
          <a-alert
            type="info"
            content="v0.9 固定主链路为混合检索；旧的单向量或单关键词模式不再作为用户可选项。Rerank 是 Quick Q&A 必需阶段。"
          />
          <div class="settings-status-grid retrieval-fixed-status">
            <article class="settings-status-card">
              <header>
                <strong>Qdrant</strong>
                <a-tag color="green">{{ qdrantStatusText }}</a-tag>
              </header>
              <p>dense vector retrieval，固定 topK {{ retrieval.retrievalEmbeddingTopK }}，threshold {{ retrieval.retrievalVectorThreshold }}。</p>
            </article>
            <article class="settings-status-card">
              <header>
                <strong>ParadeDB BM25</strong>
                <a-tag color="arcoblue">{{ paradeDbStatusText }}</a-tag>
              </header>
              <p>keyword retrieval 固定使用 pg_search BM25，keyword topK {{ retrieval.retrievalKeywordTopK }}。</p>
            </article>
            <article class="settings-status-card">
              <header>
                <strong>rerank 必需</strong>
                <a-tag :color="rerankStatusColor">{{ rerankStatusText }}</a-tag>
              </header>
              <p>RRF top{{ retrieval.retrievalRrfTopK }} 后强制 rerank top{{ retrieval.retrievalRerankTopK }}。</p>
            </article>
          </div>
          <div class="form-grid">
            <a-form-item label="embedding topK">
              <a-input-number v-model="retrieval.retrievalEmbeddingTopK" data-testid="retrieval-embedding-top-k" disabled />
            </a-form-item>
            <a-form-item label="vector threshold">
              <a-input-number v-model="retrieval.retrievalVectorThreshold" data-testid="retrieval-vector-threshold" disabled />
            </a-form-item>
            <a-form-item label="keyword topK">
              <a-input-number v-model="retrieval.retrievalKeywordTopK" data-testid="retrieval-keyword-top-k" disabled />
            </a-form-item>
            <a-form-item label="keyword threshold">
              <a-input-number v-model="retrieval.retrievalKeywordThreshold" data-testid="retrieval-keyword-threshold" disabled />
            </a-form-item>
            <a-form-item label="RRF K">
              <a-input-number v-model="retrieval.retrievalRrfK" data-testid="retrieval-rrf-k" disabled />
            </a-form-item>
            <a-form-item label="vector weight">
              <a-input-number v-model="retrieval.retrievalRrfVectorWeight" data-testid="retrieval-rrf-vector-weight" disabled />
            </a-form-item>
            <a-form-item label="keyword weight">
              <a-input-number v-model="retrieval.retrievalRrfKeywordWeight" data-testid="retrieval-rrf-keyword-weight" disabled />
            </a-form-item>
            <a-form-item label="rerank model">
              <a-select v-model="retrieval.selectedRerankModelId" data-testid="rerank-model-select" allow-clear>
                <a-option v-for="model in modelStore.rerankModels" :key="model.id" :value="model.id">
                  {{ model.name }} · {{ model.model_name }}
                </a-option>
              </a-select>
            </a-form-item>
            <a-form-item label="rerank topK">
              <a-input-number v-model="retrieval.retrievalRerankTopK" data-testid="retrieval-rerank-top-k" disabled />
            </a-form-item>
            <a-form-item label="rerank threshold">
              <a-input-number v-model="retrieval.retrievalRerankThreshold" data-testid="retrieval-rerank-threshold" disabled />
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
              <a-tag>auto</a-tag>
            </a-form-item>
            <a-form-item label="chunk size">
              <a-tag>512</a-tag>
            </a-form-item>
            <a-form-item label="overlap">
              <a-tag>80</a-tag>
            </a-form-item>
            <a-form-item label="separators">
              <a-tag>"\n\n", "\n", "。"</a-tag>
            </a-form-item>
            <a-form-item label="token limit">
              <a-tag>0</a-tag>
            </a-form-item>
            <a-form-item label="languages">
              <a-tag>未指定</a-tag>
            </a-form-item>
            <a-form-item label="Parent-Child">
              <a-tag color="green">parent-child 固定启用</a-tag>
            </a-form-item>
            <a-form-item label="parent size">
              <a-tag>4096</a-tag>
            </a-form-item>
            <a-form-item label="child size">
              <a-tag>384</a-tag>
            </a-form-item>
          </div>
          <ChunkPreview />
        </a-tab-pane>
      </a-tabs>
    </section>
  </main>
</template>
