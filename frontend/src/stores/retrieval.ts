import { ref } from "vue";
import { defineStore } from "pinia";
import { getJson, postJson, putJson } from "../utils/api";
import type {
  ChunkingConfig,
  ParserEngine,
  ParserEngineRule,
  PreviewChunkingResponse,
  RetrievalConfig,
} from "../types/api";

function parseList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.replaceAll("\\n", "\n").trim())
    .filter(Boolean);
}

function numberOrDefault(value: number, fallback: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

export const useRetrievalStore = defineStore("retrieval", () => {
  const retrievalMode = ref("hybrid");
  const retrievalEmbeddingTopK = ref(50);
  const retrievalVectorThreshold = ref(0.15);
  const retrievalKeywordThreshold = ref(0.3);
  const retrievalRerankTopK = ref(10);
  const retrievalRerankThreshold = ref(0.2);
  const selectedRerankModelId = ref("");
  const retrievalEnableRerank = ref(false);
  const retrievalRrfK = ref(60);
  const retrievalRrfVectorWeight = ref(0.7);
  const retrievalRrfKeywordWeight = ref(0.3);

  const parserEngines = ref<ParserEngine[]>([]);
  const parserEngineRules = ref<ParserEngineRule[]>([
    { file_types: ["pdf"], engine: "builtin" },
    { file_types: ["docx"], engine: "builtin" },
    { file_types: ["md", "markdown"], engine: "builtin" },
    { file_types: ["txt"], engine: "builtin" },
    { file_types: ["csv", "json", "xlsx"], engine: "builtin" },
  ]);

  const chunkStrategy = ref("auto");
  const chunkSize = ref(512);
  const chunkOverlap = ref(80);
  const separatorsText = ref("\\n\\n,\\n,。");
  const tokenLimit = ref(0);
  const languagesText = ref("");
  const enableParentChild = ref(false);
  const parentChunkSize = ref(4096);
  const childChunkSize = ref(384);
  const previewSample = ref("# 产品手册\n\n## 安装\n\n安装步骤一。安装步骤二。\n\n## 使用\n\n使用说明一。使用说明二。");
  const previewResult = ref<PreviewChunkingResponse | null>(null);

  const loading = ref(false);
  const saving = ref(false);
  const previewing = ref(false);

  function applyRetrievalConfig(config: RetrievalConfig) {
    retrievalMode.value = config.retrieval_mode || "hybrid";
    retrievalEmbeddingTopK.value = config.embedding_top_k;
    retrievalVectorThreshold.value = config.vector_threshold;
    retrievalKeywordThreshold.value = config.keyword_threshold;
    retrievalRerankTopK.value = config.rerank_top_k;
    retrievalRerankThreshold.value = config.rerank_threshold;
    selectedRerankModelId.value = config.rerank_model_id || selectedRerankModelId.value || "";
    retrievalEnableRerank.value = Boolean(config.enable_rerank);
    retrievalRrfK.value = config.rrf_k;
    retrievalRrfVectorWeight.value = config.rrf_vector_weight;
    retrievalRrfKeywordWeight.value = config.rrf_keyword_weight;
  }

  function chunkingPayload(): ChunkingConfig {
    const separators = parseList(separatorsText.value);
    return {
      strategy: chunkStrategy.value,
      chunk_size: numberOrDefault(chunkSize.value, 512),
      chunk_overlap: Math.max(0, Number(chunkOverlap.value || 0)),
      separators: separators.length ? separators : ["\n\n", "\n", "。"],
      token_limit: Math.max(0, Number(tokenLimit.value || 0)),
      languages: parseList(languagesText.value),
      enable_parent_child: enableParentChild.value,
      parent_chunk_size: numberOrDefault(parentChunkSize.value, 4096),
      child_chunk_size: numberOrDefault(childChunkSize.value, 384),
    };
  }

  function parserEngineRulesPayload(): ParserEngineRule[] {
    return parserEngineRules.value.map((rule) => ({
      file_types: rule.file_types,
      engine: rule.engine,
    }));
  }

  async function loadRetrievalConfig() {
    loading.value = true;
    try {
      const config = await getJson<RetrievalConfig>("/retrieval-config");
      applyRetrievalConfig(config);
      return config;
    } finally {
      loading.value = false;
    }
  }

  async function saveRetrievalConfig() {
    saving.value = true;
    try {
      const config = await putJson<RetrievalConfig, RetrievalConfig>("/retrieval-config", {
        retrieval_mode: retrievalMode.value,
        embedding_top_k: Number(retrievalEmbeddingTopK.value),
        vector_threshold: Number(retrievalVectorThreshold.value),
        keyword_threshold: Number(retrievalKeywordThreshold.value),
        rerank_top_k: Number(retrievalRerankTopK.value),
        rerank_threshold: Number(retrievalRerankThreshold.value),
        rerank_model_id: selectedRerankModelId.value || null,
        enable_rerank: retrievalEnableRerank.value,
        rrf_k: Number(retrievalRrfK.value),
        rrf_vector_weight: Number(retrievalRrfVectorWeight.value),
        rrf_keyword_weight: Number(retrievalRrfKeywordWeight.value),
      });
      applyRetrievalConfig(config);
      return config;
    } finally {
      saving.value = false;
    }
  }

  async function loadParserEngines() {
    parserEngines.value = await getJson<ParserEngine[]>("/parser-engines");
  }

  async function previewChunking() {
    previewing.value = true;
    try {
      previewResult.value = await postJson<PreviewChunkingResponse>("/chunker/preview", {
        text: previewSample.value,
        chunking_config: chunkingPayload(),
      });
      return previewResult.value;
    } finally {
      previewing.value = false;
    }
  }

  return {
    retrievalMode,
    retrievalEmbeddingTopK,
    retrievalVectorThreshold,
    retrievalKeywordThreshold,
    retrievalRerankTopK,
    retrievalRerankThreshold,
    selectedRerankModelId,
    retrievalEnableRerank,
    retrievalRrfK,
    retrievalRrfVectorWeight,
    retrievalRrfKeywordWeight,
    parserEngines,
    parserEngineRules,
    chunkStrategy,
    chunkSize,
    chunkOverlap,
    separatorsText,
    tokenLimit,
    languagesText,
    enableParentChild,
    parentChunkSize,
    childChunkSize,
    previewSample,
    previewResult,
    loading,
    saving,
    previewing,
    loadRetrievalConfig,
    saveRetrievalConfig,
    loadParserEngines,
    previewChunking,
    chunkingPayload,
    parserEngineRulesPayload,
  };
});
