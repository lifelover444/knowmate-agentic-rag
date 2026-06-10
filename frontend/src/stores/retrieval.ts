import { ref } from "vue";
import { defineStore } from "pinia";
import { getJson, postJson, putJson } from "../utils/api";
import type {
  ChunkingConfig,
  ParserEngine,
  ParserEngineRule,
  PreviewChunkingResponse,
  RetrievalConfig,
  RuntimeStatus,
} from "../types/api";

export const FIXED_V09_CHUNKING_CONFIG: ChunkingConfig = {
  strategy: "auto",
  chunk_size: 512,
  chunk_overlap: 80,
  separators: ["\n\n", "\n", "。"],
  token_limit: 0,
  languages: [],
  enable_parent_child: true,
  parent_chunk_size: 4096,
  child_chunk_size: 384,
};

export const useRetrievalStore = defineStore("retrieval", () => {
  const retrievalMode = ref("hybrid");
  const retrievalEmbeddingTopK = ref(50);
  const retrievalKeywordTopK = ref(50);
  const retrievalVectorThreshold = ref(0.15);
  const retrievalKeywordThreshold = ref(0.2);
  const retrievalRerankTopK = ref(8);
  const retrievalRerankThreshold = ref(0.2);
  const selectedRerankModelId = ref("");
  const retrievalEnableRerank = ref(true);
  const retrievalRrfK = ref(60);
  const retrievalRrfVectorWeight = ref(0.65);
  const retrievalRrfKeywordWeight = ref(0.35);
  const retrievalRrfTopK = ref(30);

  const parserEngines = ref<ParserEngine[]>([]);
  const runtimeStatus = ref<RuntimeStatus | null>(null);
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
  const enableParentChild = ref(true);
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
    retrievalKeywordTopK.value = config.keyword_top_k || 50;
    retrievalVectorThreshold.value = config.vector_threshold;
    retrievalKeywordThreshold.value = config.keyword_threshold;
    retrievalRerankTopK.value = config.rerank_top_k;
    retrievalRerankThreshold.value = config.rerank_threshold;
    selectedRerankModelId.value = config.rerank_model_id || selectedRerankModelId.value || "";
    retrievalEnableRerank.value = Boolean(config.enable_rerank);
    retrievalRrfK.value = config.rrf_k;
    retrievalRrfVectorWeight.value = config.rrf_vector_weight;
    retrievalRrfKeywordWeight.value = config.rrf_keyword_weight;
    retrievalRrfTopK.value = config.rrf_top_k || 30;
    chunkStrategy.value = FIXED_V09_CHUNKING_CONFIG.strategy;
    chunkSize.value = FIXED_V09_CHUNKING_CONFIG.chunk_size;
    chunkOverlap.value = FIXED_V09_CHUNKING_CONFIG.chunk_overlap;
    separatorsText.value = "\\n\\n,\\n,。";
    tokenLimit.value = FIXED_V09_CHUNKING_CONFIG.token_limit;
    languagesText.value = "";
    enableParentChild.value = true;
    parentChunkSize.value = FIXED_V09_CHUNKING_CONFIG.parent_chunk_size;
    childChunkSize.value = FIXED_V09_CHUNKING_CONFIG.child_chunk_size;
  }

  function chunkingPayload(): ChunkingConfig {
    return {
      ...FIXED_V09_CHUNKING_CONFIG,
      separators: ["\n\n", "\n", "。"],
      languages: [],
      enable_parent_child: true,
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
        rerank_model_id: selectedRerankModelId.value || null,
        retrieval_mode: "hybrid",
        vector_engine: "qdrant",
        keyword_engine: "paradedb_bm25",
        embedding_top_k: 50,
        keyword_top_k: 50,
        vector_threshold: 0.15,
        keyword_threshold: 0.2,
        rerank_top_k: 8,
        rerank_threshold: 0.2,
        enable_rerank: true,
        rrf_k: 60,
        rrf_vector_weight: 0.65,
        rrf_keyword_weight: 0.35,
        rrf_top_k: 30,
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

  async function loadRuntimeStatus() {
    runtimeStatus.value = await getJson<RuntimeStatus>("/runtime-status");
    parserEngines.value = runtimeStatus.value.parser_engines;
    return runtimeStatus.value;
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
    retrievalKeywordTopK,
    retrievalVectorThreshold,
    retrievalKeywordThreshold,
    retrievalRerankTopK,
    retrievalRerankThreshold,
    selectedRerankModelId,
    retrievalEnableRerank,
    retrievalRrfK,
    retrievalRrfVectorWeight,
    retrievalRrfKeywordWeight,
    retrievalRrfTopK,
    parserEngines,
    runtimeStatus,
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
    loadRuntimeStatus,
    previewChunking,
    chunkingPayload,
    parserEngineRulesPayload,
  };
});
