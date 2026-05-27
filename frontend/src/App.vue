<script setup>
import {
  BookOpen,
  CheckCircle2,
  FileText,
  KeyRound,
  Loader2,
  MessageSquareText,
  Play,
  RefreshCcw,
  Save,
  Search,
  SlidersHorizontal,
  UploadCloud,
} from "lucide-vue-next";
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { formatApiError } from "./apiErrors.js";

const apiBase = "/api/v1";
const documentProcessingMaxPolls = 300;
const qwenPresets = {
  cn: {
    baseUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    chatModel: "qwen-plus",
    embeddingModel: "text-embedding-v4",
    embeddingDimension: 1024,
  },
  intl: {
    baseUrl: "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    chatModel: "qwen-plus",
    embeddingModel: "text-embedding-v4",
    embeddingDimension: 1024,
  },
};
const deepseekPreset = {
  baseUrl: "https://api.deepseek.com/v1",
  modelName: "deepseek-chat",
};

const qaProvider = ref("qwen");
const qaRegion = ref("cn");
const qaConfigName = ref("阿里云百炼 Qwen QA");
const qaBaseUrl = ref(qwenPresets.cn.baseUrl);
const qaApiKey = ref("");
const qaApiKeyLast4 = ref("");
const qaApiKeyConfigured = ref(false);
const qaModelName = ref(qwenPresets.cn.chatModel);
const embeddingProvider = ref("qwen");
const embeddingRegion = ref("cn");
const embeddingConfigName = ref("阿里云百炼 Qwen Embedding");
const embeddingBaseUrl = ref(qwenPresets.cn.baseUrl);
const embeddingApiKey = ref("");
const embeddingApiKeyLast4 = ref("");
const embeddingApiKeyConfigured = ref(false);
const embeddingModelName = ref(qwenPresets.cn.embeddingModel);
const embeddingDimension = ref(qwenPresets.cn.embeddingDimension);
const modelReady = ref(false);
const testingQaModel = ref(false);
const testingEmbeddingModel = ref(false);
const savingQaModel = ref(false);
const savingEmbeddingModel = ref(false);
const qaModelTestResult = ref(null);
const embeddingModelTestResult = ref(null);
const applyingSavedConfig = ref(false);
const models = ref([]);
const selectedChatModelId = ref("");
const selectedEmbeddingModelId = ref("");
const selectedRerankModelId = ref("");
const retrievalMode = ref("hybrid");
const retrievalEmbeddingTopK = ref(50);
const retrievalVectorThreshold = ref(0.15);
const retrievalKeywordThreshold = ref(0.3);
const retrievalRerankTopK = ref(10);
const retrievalRerankThreshold = ref(0.2);
const retrievalRrfK = ref(60);
const retrievalRrfVectorWeight = ref(0.7);
const retrievalRrfKeywordWeight = ref(0.3);
const retrievalEnableRerank = ref(false);
const savingRetrieval = ref(false);
const reprocessingDocument = ref(false);
const reprocessingKnowledgeBase = ref(false);

const parserEngines = ref([]);
const parserEngineRules = ref([
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
const previewResult = ref(null);
const previewing = ref(false);

const kbName = ref(`知友测试知识库-${new Date().toLocaleTimeString("zh-CN", { hour12: false })}`);
const kbDescription = ref("用于验证知识库创建、文档上传、切片入库、向量检索和快速问答的测试知识库。");
const knowledgeBase = ref(null);
const documentRecord = ref(null);
const chunks = ref([]);
const selectedFile = ref(null);
const question = ref("知友能做什么？");
const quickAnswer = ref(null);
const knowledgeSearchResult = ref(null);
const knowledgeSearchQuery = ref("混合检索");
const searchingKnowledge = ref(false);
const busy = ref(false);
const uploading = ref(false);
const polling = ref(false);
const answering = ref(false);
const errorMessage = ref("");
const eventLog = ref([]);

const qaApiKeyHint = computed(() => {
  if (qaApiKeyConfigured.value && qaApiKeyLast4.value) {
    return `QA 模型 Key 已配置，尾号 ****${qaApiKeyLast4.value}。留空保存将继续使用旧 Key。`;
  }
  return "请输入 QA 模型服务 API Key，保存后后端加密存储。";
});

const embeddingApiKeyHint = computed(() => {
  if (embeddingApiKeyConfigured.value && embeddingApiKeyLast4.value) {
    return `向量模型 Key 已配置，尾号 ****${embeddingApiKeyLast4.value}。留空保存将继续使用旧 Key。`;
  }
  return "请输入向量模型服务 API Key，保存后后端加密存储。";
});

const uploadHint = computed(() => {
  if (!selectedChatModelId.value || !selectedEmbeddingModelId.value) return "请先创建并选择对话模型和向量模型。";
  if (!knowledgeBase.value) return "请先创建知识库。";
  if (!selectedFile.value) return "请选择要上传的文档。";
  return "";
});

const pipeline = computed(() => [
  {
    label: "模型配置",
    done: modelReady.value,
    active: testingQaModel.value || testingEmbeddingModel.value || savingQaModel.value || savingEmbeddingModel.value,
  },
  { label: "知识库", done: Boolean(knowledgeBase.value), active: busy.value },
  { label: "上传", done: Boolean(documentRecord.value), active: uploading.value },
  {
    label: "解析",
    done: documentRecord.value?.parse_status === "completed",
    active: polling.value && documentRecord.value?.parse_status !== "completed",
  },
  { label: "切片入库", done: chunks.value.length > 0, active: false },
  { label: "问答", done: Boolean(quickAnswer.value?.answer), active: answering.value },
]);

watch([qaProvider, qaRegion], () => {
  if (applyingSavedConfig.value) return;
  if (qaProvider.value === "qwen") {
    const preset = qwenPresets[qaRegion.value];
    qaConfigName.value = "阿里云百炼 Qwen QA";
    qaBaseUrl.value = preset.baseUrl;
    qaModelName.value = preset.chatModel;
  }
  if (qaProvider.value === "deepseek") {
    qaConfigName.value = "DeepSeek QA";
    qaBaseUrl.value = deepseekPreset.baseUrl;
    qaModelName.value = deepseekPreset.modelName;
  }
  qaModelTestResult.value = null;
});

watch([embeddingProvider, embeddingRegion], () => {
  if (applyingSavedConfig.value) return;
  if (embeddingProvider.value !== "qwen") return;
  const preset = qwenPresets[embeddingRegion.value];
  embeddingConfigName.value = "阿里云百炼 Qwen Embedding";
  embeddingBaseUrl.value = preset.baseUrl;
  embeddingModelName.value = preset.embeddingModel;
  embeddingDimension.value = preset.embeddingDimension;
  embeddingModelTestResult.value = null;
});

watch(
  [selectedChatModelId, selectedEmbeddingModelId],
  () => {
    modelReady.value = Boolean(selectedChatModelId.value && selectedEmbeddingModelId.value);
  },
);

watch([qaBaseUrl, qaApiKey, qaModelName], () => {
  if (applyingSavedConfig.value) return;
  qaModelTestResult.value = null;
});

watch([embeddingBaseUrl, embeddingApiKey, embeddingModelName, embeddingDimension], () => {
  if (applyingSavedConfig.value) return;
  embeddingModelTestResult.value = null;
});

const chatModels = computed(() => models.value.filter((item) => item.type === "KnowledgeQA"));
const embeddingModels = computed(() => models.value.filter((item) => item.type === "Embedding"));
const rerankModels = computed(() => models.value.filter((item) => item.type === "Rerank"));

function log(message) {
  eventLog.value.unshift(`${new Date().toLocaleTimeString("zh-CN", { hour12: false })} ${message}`);
  eventLog.value = eventLog.value.slice(0, 8);
}

function handleError(error) {
  errorMessage.value = error instanceof Error ? error.message : formatApiError(error);
}

function statusText(status) {
  return (
    {
      pending: "等待解析",
      processing: "解析中",
      completed: "解析完成",
      failed: "解析失败",
      enabled: "已启用",
      disabled: "已停用",
    }[status] || status
  );
}

function modelEntityPayload(type) {
  if (type === "Embedding") {
    return {
      name: embeddingConfigName.value.trim() || "Qwen Embedding",
      type,
      provider: embeddingProvider.value,
      source: "remote",
      base_url: embeddingBaseUrl.value.trim(),
      api_key: embeddingApiKey.value.trim() || undefined,
      model_name: embeddingModelName.value.trim(),
      embedding_dimension: Number(embeddingDimension.value),
    };
  }
  return {
    name: qaConfigName.value.trim() || (qaProvider.value === "deepseek" ? "DeepSeek QA" : "Qwen QA"),
    type,
    provider: qaProvider.value,
    source: "remote",
    base_url: qaBaseUrl.value.trim(),
    api_key: qaApiKey.value.trim() || undefined,
    model_name: qaModelName.value.trim(),
  };
}

function modelTestPayload(type) {
  const payload = modelEntityPayload(type);
  const apiKey = type === "Embedding" ? embeddingApiKey.value.trim() : qaApiKey.value.trim();
  const modelId = type === "Embedding" ? selectedEmbeddingModelId.value : selectedChatModelId.value;
  return {
    ...payload,
    model_id: modelId || undefined,
    api_key: apiKey || undefined,
    embedding_dimension: type === "Embedding" ? Number(embeddingDimension.value) : 1,
  };
}

function parseList(value) {
  return value
    .split(",")
    .map((item) => item.replaceAll("\\n", "\n").trim())
    .filter(Boolean);
}

function numberOrDefault(value, fallback) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function chunkingPayload() {
  return {
    strategy: chunkStrategy.value,
    chunk_size: numberOrDefault(chunkSize.value, 512),
    chunk_overlap: Math.max(0, Number(chunkOverlap.value || 0)),
    separators: parseList(separatorsText.value).length ? parseList(separatorsText.value) : ["\n\n", "\n", "。"],
    token_limit: Math.max(0, Number(tokenLimit.value || 0)),
    languages: parseList(languagesText.value),
    enable_parent_child: enableParentChild.value,
    parent_chunk_size: numberOrDefault(parentChunkSize.value, 4096),
    child_chunk_size: numberOrDefault(childChunkSize.value, 384),
  };
}

function parserEngineRulesPayload() {
  return parserEngineRules.value.map((rule) => ({
    file_types: rule.file_types,
    engine: rule.engine,
  }));
}

function handleFileSelected(event) {
  errorMessage.value = "";
  selectedFile.value = event.target.files?.[0] || null;
}

async function request(path, options = {}) {
  const response = await fetch(`${apiBase}${path}`, options);
  const text = await response.text();
  const payload = parseResponsePayload(text);
  if (!response.ok) {
    throw new Error(formatApiError(payload, text || `HTTP ${response.status}`));
  }
  return payload;
}

function parseResponsePayload(text) {
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

async function jsonRequest(path, method, payload) {
  return request(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

function applySavedConfig(config) {
  if (!config) return;
  applyingSavedConfig.value = true;
  qaProvider.value = config.provider;
  qaConfigName.value = config.name;
  qaBaseUrl.value = config.base_url;
  qaModelName.value = config.chat_model;
  embeddingProvider.value = config.provider;
  embeddingConfigName.value = `${config.name} Embedding`;
  embeddingBaseUrl.value = config.base_url;
  embeddingModelName.value = config.embedding_model;
  embeddingDimension.value = config.embedding_dimension;
  qaApiKeyConfigured.value = config.api_key_configured;
  qaApiKeyLast4.value = config.api_key_last4 || "";
  embeddingApiKeyConfigured.value = config.api_key_configured;
  embeddingApiKeyLast4.value = config.api_key_last4 || "";
  qaApiKey.value = "";
  embeddingApiKey.value = "";
  nextTick(() => {
    applyingSavedConfig.value = false;
  });
}

async function loadModelConfig() {
  try {
    const config = await request("/model-config");
    applySavedConfig(config);
  } catch (error) {
    handleError(error);
  }
}

async function loadModels() {
  try {
    models.value = await request("/models");
    if (!chatModels.value.some((item) => item.id === selectedChatModelId.value)) {
      selectedChatModelId.value = chatModels.value[0]?.id || "";
    }
    if (!embeddingModels.value.some((item) => item.id === selectedEmbeddingModelId.value)) {
      selectedEmbeddingModelId.value = embeddingModels.value[0]?.id || "";
    }
    if (!rerankModels.value.some((item) => item.id === selectedRerankModelId.value)) {
      selectedRerankModelId.value = rerankModels.value[0]?.id || "";
    }
    applySelectedQaModel();
    applySelectedEmbeddingModel();
    modelReady.value = Boolean(selectedChatModelId.value && selectedEmbeddingModelId.value);
  } catch (error) {
    handleError(new Error(`加载模型列表失败：${error.message || formatApiError(error)}`));
  }
}

async function loadRetrievalConfig() {
  try {
    const config = await request("/retrieval-config");
    retrievalMode.value = config.retrieval_mode || "hybrid";
    retrievalEmbeddingTopK.value = config.embedding_top_k;
    retrievalVectorThreshold.value = config.vector_threshold;
    retrievalKeywordThreshold.value = config.keyword_threshold;
    retrievalRerankTopK.value = config.rerank_top_k;
    retrievalRerankThreshold.value = config.rerank_threshold;
    retrievalRrfK.value = config.rrf_k;
    retrievalRrfVectorWeight.value = config.rrf_vector_weight;
    retrievalRrfKeywordWeight.value = config.rrf_keyword_weight;
    retrievalEnableRerank.value = Boolean(config.enable_rerank);
    selectedRerankModelId.value = config.rerank_model_id || selectedRerankModelId.value;
  } catch (error) {
    handleError(error);
  }
}

async function loadParserEngines() {
  try {
    parserEngines.value = await request("/parser-engines");
  } catch (error) {
    handleError(error);
  }
}

function applySelectedQaModel() {
  const model = chatModels.value.find((item) => item.id === selectedChatModelId.value);
  if (!model) return;
  applyingSavedConfig.value = true;
  qaProvider.value = model.provider;
  qaConfigName.value = model.name;
  qaBaseUrl.value = model.base_url;
  qaModelName.value = model.model_name;
  qaApiKeyConfigured.value = model.api_key_configured;
  qaApiKeyLast4.value = model.api_key_last4 || "";
  qaApiKey.value = "";
  nextTick(() => {
    applyingSavedConfig.value = false;
  });
}

function applySelectedEmbeddingModel() {
  const model = embeddingModels.value.find((item) => item.id === selectedEmbeddingModelId.value);
  if (!model) return;
  applyingSavedConfig.value = true;
  embeddingProvider.value = model.provider;
  embeddingConfigName.value = model.name;
  embeddingBaseUrl.value = model.base_url;
  embeddingModelName.value = model.model_name;
  embeddingDimension.value = model.embedding_dimension || embeddingDimension.value;
  embeddingApiKeyConfigured.value = model.api_key_configured;
  embeddingApiKeyLast4.value = model.api_key_last4 || "";
  embeddingApiKey.value = "";
  nextTick(() => {
    applyingSavedConfig.value = false;
  });
}

async function testQaModel() {
  testingQaModel.value = true;
  errorMessage.value = "";
  try {
    qaModelTestResult.value = await jsonRequest("/models/test", "POST", modelTestPayload("KnowledgeQA"));
    log(qaModelTestResult.value.chat_ok ? "QA 模型连接测试通过" : "QA 模型连接测试未通过");
  } catch (error) {
    qaModelTestResult.value = null;
    handleError(error);
  } finally {
    testingQaModel.value = false;
  }
}

async function testEmbeddingModel() {
  testingEmbeddingModel.value = true;
  errorMessage.value = "";
  try {
    embeddingModelTestResult.value = await jsonRequest("/models/test", "POST", modelTestPayload("Embedding"));
    log(embeddingModelTestResult.value.embedding_ok ? "向量模型连接测试通过" : "向量模型连接测试未通过");
  } catch (error) {
    embeddingModelTestResult.value = null;
    handleError(error);
  } finally {
    testingEmbeddingModel.value = false;
  }
}

async function saveQaModel() {
  savingQaModel.value = true;
  errorMessage.value = "";
  try {
    const chatPayload = modelEntityPayload("KnowledgeQA");
    if (!qaApiKey.value.trim() && !selectedChatModelId.value) {
      throw new Error("首次创建 QA 模型必须填写 API Key。");
    }
    const chatConfig = selectedChatModelId.value
      ? await jsonRequest(`/models/${selectedChatModelId.value}`, "PUT", chatPayload)
      : await jsonRequest("/models", "POST", chatPayload);
    if (qaApiKey.value.trim()) {
      await jsonRequest(`/models/${chatConfig.id}/credentials`, "PUT", { api_key: qaApiKey.value.trim() });
      qaApiKeyLast4.value = qaApiKey.value.trim().slice(-4);
    }
    selectedChatModelId.value = chatConfig.id;
    qaApiKeyConfigured.value = true;
    qaApiKey.value = "";
    await loadModels();
    log("QA 模型已保存");
  } catch (error) {
    handleError(error);
  } finally {
    savingQaModel.value = false;
  }
}

async function saveEmbeddingModel() {
  savingEmbeddingModel.value = true;
  errorMessage.value = "";
  try {
    const embeddingPayload = modelEntityPayload("Embedding");
    if (!embeddingApiKey.value.trim() && !selectedEmbeddingModelId.value) {
      throw new Error("首次创建向量模型必须填写 API Key。");
    }
    const embeddingConfig = selectedEmbeddingModelId.value
      ? await jsonRequest(`/models/${selectedEmbeddingModelId.value}`, "PUT", embeddingPayload)
      : await jsonRequest("/models", "POST", embeddingPayload);
    if (embeddingApiKey.value.trim()) {
      await jsonRequest(`/models/${embeddingConfig.id}/credentials`, "PUT", {
        api_key: embeddingApiKey.value.trim(),
      });
      embeddingApiKeyLast4.value = embeddingApiKey.value.trim().slice(-4);
    }
    selectedEmbeddingModelId.value = embeddingConfig.id;
    embeddingApiKeyConfigured.value = true;
    embeddingApiKey.value = "";
    await loadModels();
    log("向量模型已保存");
  } catch (error) {
    handleError(error);
  } finally {
    savingEmbeddingModel.value = false;
  }
}

async function saveRetrievalConfig() {
  savingRetrieval.value = true;
  errorMessage.value = "";
  try {
    const config = await jsonRequest("/retrieval-config", "PUT", {
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
    retrievalMode.value = config.retrieval_mode;
    retrievalEmbeddingTopK.value = config.embedding_top_k;
    retrievalVectorThreshold.value = config.vector_threshold;
    retrievalKeywordThreshold.value = config.keyword_threshold;
    retrievalRerankTopK.value = config.rerank_top_k;
    retrievalRerankThreshold.value = config.rerank_threshold;
    retrievalRrfK.value = config.rrf_k;
    retrievalRrfVectorWeight.value = config.rrf_vector_weight;
    retrievalRrfKeywordWeight.value = config.rrf_keyword_weight;
    retrievalEnableRerank.value = config.enable_rerank;
    selectedRerankModelId.value = config.rerank_model_id || "";
    log("检索配置已保存");
  } catch (error) {
    handleError(error);
  } finally {
    savingRetrieval.value = false;
  }
}

async function createKnowledgeBase() {
  busy.value = true;
  errorMessage.value = "";
  quickAnswer.value = null;
  chunks.value = [];
  documentRecord.value = null;
  try {
    knowledgeBase.value = await jsonRequest("/knowledge-bases", "POST", {
      name: kbName.value.trim() || "knowmate-test",
      description: kbDescription.value.trim() || null,
      embedding_model_id: selectedEmbeddingModelId.value,
      summary_model_id: selectedChatModelId.value,
      chunking_config: chunkingPayload(),
      parser_engine_rules: parserEngineRulesPayload(),
    });
    log(`创建知识库 ${knowledgeBase.value.name}`);
  } catch (error) {
    handleError(error);
  } finally {
    busy.value = false;
  }
}

async function reprocessCurrentDocument() {
  if (!documentRecord.value) return;
  reprocessingDocument.value = true;
  errorMessage.value = "";
  try {
    documentRecord.value = await request(`/documents/${documentRecord.value.id}/reprocess`, { method: "POST" });
    chunks.value = await request(`/documents/${documentRecord.value.id}/chunks`);
    log("文档已重新处理并重建向量");
  } catch (error) {
    handleError(error);
  } finally {
    reprocessingDocument.value = false;
  }
}

async function reprocessCurrentKnowledgeBase() {
  if (!knowledgeBase.value) return;
  reprocessingKnowledgeBase.value = true;
  errorMessage.value = "";
  try {
    const result = await request(`/knowledge-bases/${knowledgeBase.value.id}/reprocess`, { method: "POST" });
    if (documentRecord.value) {
      documentRecord.value = await request(`/documents/${documentRecord.value.id}`);
      chunks.value = await request(`/documents/${documentRecord.value.id}/chunks`);
    }
    log(`知识库重建已提交 ${result.queued} 个文档`);
  } catch (error) {
    handleError(error);
  } finally {
    reprocessingKnowledgeBase.value = false;
  }
}

async function previewChunking() {
  previewing.value = true;
  errorMessage.value = "";
  previewResult.value = null;
  try {
    previewResult.value = await jsonRequest("/chunker/preview", "POST", {
      text: previewSample.value,
      chunking_config: chunkingPayload(),
    });
    log(`预览切片 ${previewResult.value.stats.count}`);
  } catch (error) {
    handleError(error);
  } finally {
    previewing.value = false;
  }
}

async function uploadDocument() {
  if (uploadHint.value) {
    errorMessage.value = uploadHint.value;
    return;
  }
  uploading.value = true;
  errorMessage.value = "";
  quickAnswer.value = null;
  chunks.value = [];
  try {
    const formData = new FormData();
    formData.append("file", selectedFile.value);
    documentRecord.value = await request(`/knowledge-bases/${knowledgeBase.value.id}/documents/file`, {
      method: "POST",
      body: formData,
    });
    log(`上传 ${documentRecord.value.file_name || documentRecord.value.title}`);
    await pollDocument();
  } catch (error) {
    handleError(error);
  } finally {
    uploading.value = false;
  }
}

async function pollDocument() {
  if (!documentRecord.value) return;
  polling.value = true;
  try {
    for (let index = 0; index < documentProcessingMaxPolls; index += 1) {
      documentRecord.value = await request(`/documents/${documentRecord.value.id}`);
      if (documentRecord.value.parse_status === "completed") {
        log("文档解析完成");
        chunks.value = await request(`/documents/${documentRecord.value.id}/chunks`);
        log(`切片 ${chunks.value.length}`);
        return;
      }
      if (documentRecord.value.parse_status === "failed") {
        throw new Error(documentRecord.value.error_message || "文档解析失败");
      }
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
    throw new Error("文档解析超时");
  } finally {
    polling.value = false;
  }
}

async function askQuestion() {
  if (!modelReady.value || !knowledgeBase.value || !question.value.trim()) return;
  answering.value = true;
  errorMessage.value = "";
  try {
    quickAnswer.value = await jsonRequest("/quick-answer", "POST", {
      knowledge_base_id: knowledgeBase.value.id,
      query: question.value.trim(),
      top_k: Number(retrievalRerankTopK.value || 5),
      mode: retrievalMode.value,
      enable_rerank: retrievalEnableRerank.value,
    });
    log(`返回来源 ${quickAnswer.value.sources.length}`);
  } catch (error) {
    handleError(error);
  } finally {
    answering.value = false;
  }
}

async function searchKnowledge() {
  if (!knowledgeBase.value || !knowledgeSearchQuery.value.trim()) return;
  searchingKnowledge.value = true;
  errorMessage.value = "";
  knowledgeSearchResult.value = null;
  try {
    knowledgeSearchResult.value = await jsonRequest("/knowledge-search", "POST", {
      knowledge_base_id: knowledgeBase.value.id,
      query: knowledgeSearchQuery.value.trim(),
      mode: retrievalMode.value,
      top_k: Number(retrievalRerankTopK.value || 5),
      enable_rerank: retrievalEnableRerank.value,
    });
    log(`知识搜索命中 ${knowledgeSearchResult.value.hits.length} 条`);
  } catch (error) {
    handleError(error);
  } finally {
    searchingKnowledge.value = false;
  }
}

onMounted(() => {
  loadModelConfig();
  loadModels();
  loadRetrievalConfig();
  loadParserEngines();
});
</script>

<template>
  <main class="shell">
    <header class="topbar">
      <div>
        <p class="eyebrow">knowmate知友</p>
        <h1>知识库快速问答测试台</h1>
      </div>
      <div class="health">
        <span class="pulse"></span>
        后端服务 / 向量库
      </div>
    </header>

    <section class="pipeline" aria-label="知识问答链路">
      <div
        v-for="item in pipeline"
        :key="item.label"
        class="step"
        :class="{ done: item.done, active: item.active }"
      >
        <CheckCircle2 v-if="item.done" :size="18" />
        <Loader2 v-else-if="item.active" :size="18" class="spin" />
        <span v-else></span>
        {{ item.label }}
      </div>
    </section>

    <p v-if="errorMessage" class="error" role="alert">{{ errorMessage }}</p>

    <section class="panel model-panel">
      <div class="panel-title">
        <SlidersHorizontal :size="20" />
        <h2>模型配置</h2>
      </div>
      <div class="model-split">
        <section class="model-subpanel">
          <h3>QA 模型（DeepSeek / Qwen）</h3>
          <div class="model-grid compact">
            <label>
              <span>绑定对话模型</span>
              <select v-model="selectedChatModelId" data-testid="chat-model-select" @change="applySelectedQaModel">
                <option value="">请选择 KnowledgeQA 模型</option>
                <option v-for="model in chatModels" :key="model.id" :value="model.id">
                  {{ model.name }} · {{ model.model_name }} · {{ model.status }}
                </option>
              </select>
            </label>
            <label>
              <span>供应商</span>
              <select v-model="qaProvider" data-testid="qa-provider">
                <option value="qwen">Qwen / DashScope</option>
                <option value="deepseek">DeepSeek</option>
                <option value="openai-compatible">OpenAI 兼容</option>
              </select>
            </label>
            <label>
              <span>区域</span>
              <select v-model="qaRegion" data-testid="qa-region" :disabled="qaProvider !== 'qwen'">
                <option value="cn">中国内地</option>
                <option value="intl">国际站</option>
              </select>
            </label>
            <label>
              <span>配置名称</span>
              <input v-model="qaConfigName" data-testid="qa-config-name" />
            </label>
            <label>
              <span>Base URL</span>
              <input v-model="qaBaseUrl" data-testid="qa-base-url" />
            </label>
            <label>
              <span>API Key</span>
              <input v-model="qaApiKey" data-testid="qa-api-key" type="password" autocomplete="off" />
              <small>{{ qaApiKeyHint }}</small>
            </label>
            <label>
              <span>模型名称</span>
              <input v-model="qaModelName" data-testid="qa-model-name" />
            </label>
          </div>
          <div class="model-actions">
            <button data-testid="test-qa-model" :disabled="testingQaModel" @click="testQaModel">
              <Loader2 v-if="testingQaModel" :size="17" class="spin" />
              <KeyRound v-else :size="17" />
              测试 QA
            </button>
            <button data-testid="save-qa-model" :disabled="savingQaModel" @click="saveQaModel">
              <Loader2 v-if="savingQaModel" :size="17" class="spin" />
              <Save v-else :size="17" />
              保存 QA 模型
            </button>
          </div>
          <p
            v-if="qaModelTestResult"
            class="model-result"
            :class="{ ok: qaModelTestResult.chat_ok }"
            data-testid="qa-model-test-result"
          >
            {{ qaModelTestResult.message }}；对话 {{ qaModelTestResult.chat_ok ? "正常" : "异常" }}
          </p>
        </section>

        <section class="model-subpanel">
          <h3>Embedding 模型（Qwen）</h3>
          <div class="model-grid compact">
            <label>
              <span>绑定向量模型</span>
              <select
                v-model="selectedEmbeddingModelId"
                data-testid="embedding-model-select"
                @change="applySelectedEmbeddingModel"
              >
                <option value="">请选择 Embedding 模型</option>
                <option v-for="model in embeddingModels" :key="model.id" :value="model.id">
                  {{ model.name }} · {{ model.model_name }} · {{ model.embedding_dimension }} 维
                </option>
              </select>
            </label>
            <label>
              <span>供应商</span>
              <select v-model="embeddingProvider" data-testid="embedding-provider">
                <option value="qwen">Qwen / DashScope</option>
                <option value="openai-compatible">OpenAI 兼容</option>
              </select>
            </label>
            <label>
              <span>区域</span>
              <select
                v-model="embeddingRegion"
                data-testid="embedding-region"
                :disabled="embeddingProvider !== 'qwen'"
              >
                <option value="cn">中国内地</option>
                <option value="intl">国际站</option>
              </select>
            </label>
            <label>
              <span>配置名称</span>
              <input v-model="embeddingConfigName" data-testid="embedding-config-name" />
            </label>
            <label>
              <span>Base URL</span>
              <input v-model="embeddingBaseUrl" data-testid="embedding-base-url" />
            </label>
            <label>
              <span>API Key</span>
              <input v-model="embeddingApiKey" data-testid="embedding-api-key" type="password" autocomplete="off" />
              <small>{{ embeddingApiKeyHint }}</small>
            </label>
            <label>
              <span>模型名称</span>
              <input v-model="embeddingModelName" data-testid="embedding-model-name" />
            </label>
            <label>
              <span>向量维度</span>
              <input
                v-model.number="embeddingDimension"
                data-testid="embedding-dimension"
                type="number"
                min="1"
              />
            </label>
          </div>
          <div class="model-actions">
            <button data-testid="test-embedding-model" :disabled="testingEmbeddingModel" @click="testEmbeddingModel">
              <Loader2 v-if="testingEmbeddingModel" :size="17" class="spin" />
              <KeyRound v-else :size="17" />
              测试向量
            </button>
            <button data-testid="save-embedding-model" :disabled="savingEmbeddingModel" @click="saveEmbeddingModel">
              <Loader2 v-if="savingEmbeddingModel" :size="17" class="spin" />
              <Save v-else :size="17" />
              保存向量模型
            </button>
          </div>
          <p
            v-if="embeddingModelTestResult"
            class="model-result"
            :class="{ ok: embeddingModelTestResult.embedding_ok }"
            data-testid="embedding-model-test-result"
          >
            {{ embeddingModelTestResult.message }}；向量
            {{ embeddingModelTestResult.embedding_ok ? "正常" : "异常" }}，检测维度
            {{ embeddingModelTestResult.detected_dimension || "-" }}
          </p>
        </section>
      </div>
      <div class="model-list" data-testid="model-list">
        <article v-for="model in models" :key="model.id">
          <strong>{{ model.type }}</strong>
          <span>{{ model.name }} / {{ model.model_name }}</span>
          <small>Key {{ model.api_key_configured ? `已配置 ****${model.api_key_last4 || ""}` : "未配置" }}</small>
        </article>
      </div>
      <div class="retrieval-config" data-testid="retrieval-config">
        <label>
          <span>检索模式</span>
          <select v-model="retrievalMode" data-testid="retrieval-mode">
            <option value="hybrid">Hybrid：向量 + 关键词</option>
            <option value="vector_only">仅向量</option>
            <option value="keyword_only">仅关键词</option>
          </select>
        </label>
        <label>
          <span>候选召回 TopK</span>
          <input v-model.number="retrievalEmbeddingTopK" data-testid="retrieval-embedding-top-k" type="number" min="1" max="500" />
        </label>
        <label>
          <span>向量阈值</span>
          <input v-model.number="retrievalVectorThreshold" data-testid="retrieval-vector-threshold" type="number" min="0" max="1" step="0.01" />
        </label>
        <label>
          <span>关键词阈值</span>
          <input v-model.number="retrievalKeywordThreshold" data-testid="retrieval-keyword-threshold" type="number" min="0" max="1" step="0.01" />
        </label>
        <label>
          <span>最终来源 TopK</span>
          <input v-model.number="retrievalRerankTopK" data-testid="retrieval-rerank-top-k" type="number" min="1" max="50" />
        </label>
        <label>
          <span>RRF K</span>
          <input v-model.number="retrievalRrfK" data-testid="retrieval-rrf-k" type="number" min="1" max="500" />
        </label>
        <label>
          <span>向量权重</span>
          <input v-model.number="retrievalRrfVectorWeight" data-testid="retrieval-rrf-vector-weight" type="number" min="0.1" max="10" step="0.1" />
        </label>
        <label>
          <span>关键词权重</span>
          <input v-model.number="retrievalRrfKeywordWeight" data-testid="retrieval-rrf-keyword-weight" type="number" min="0.1" max="10" step="0.1" />
        </label>
        <label>
          <span>Rerank 阈值</span>
          <input v-model.number="retrievalRerankThreshold" data-testid="retrieval-rerank-threshold" type="number" min="-10" max="10" step="0.01" />
        </label>
        <label>
          <span>Rerank 模型</span>
          <select v-model="selectedRerankModelId" data-testid="rerank-model-select">
            <option value="">未绑定 Rerank 模型</option>
            <option v-for="model in rerankModels" :key="model.id" :value="model.id">
              {{ model.name }} · {{ model.model_name }} · {{ model.status }}
            </option>
          </select>
        </label>
        <label class="toggle-row">
          <span>启用 Rerank</span>
          <input v-model="retrievalEnableRerank" data-testid="retrieval-enable-rerank" type="checkbox" />
        </label>
        <button data-testid="save-retrieval" :disabled="savingRetrieval" @click="saveRetrievalConfig">
          <Loader2 v-if="savingRetrieval" :size="17" class="spin" />
          <Save v-else :size="17" />
          保存检索配置
        </button>
      </div>
      <p class="model-note">知识库会绑定上方选择的 KnowledgeQA 与 Embedding 模型。切换向量模型或维度后，请重新处理文档重建向量。</p>
    </section>

    <section class="panel ingest-panel">
      <div class="panel-title">
        <SlidersHorizontal :size="20" />
        <h2>解析与切分设置</h2>
      </div>
      <div class="ingest-grid">
        <label>
          <span>PDF 解析引擎</span>
          <select v-model="parserEngineRules[0].engine" data-testid="parser-pdf">
            <option v-for="engine in parserEngines" :key="engine.name" :value="engine.name" :disabled="!engine.available">
              {{ engine.name }}{{ engine.available ? "" : "（不可用）" }}
            </option>
          </select>
        </label>
        <label>
          <span>Office 解析引擎</span>
          <select v-model="parserEngineRules[1].engine" data-testid="parser-office">
            <option v-for="engine in parserEngines" :key="engine.name" :value="engine.name" :disabled="!engine.available">
              {{ engine.name }}{{ engine.available ? "" : "（不可用）" }}
            </option>
          </select>
        </label>
        <label>
          <span>切分策略</span>
          <select v-model="chunkStrategy" data-testid="chunk-strategy">
            <option value="auto">自动：标题 → 启发式 → 传统递归</option>
            <option value="heading">标题优先</option>
            <option value="heuristic">启发式边界</option>
            <option value="legacy">传统递归</option>
          </select>
        </label>
        <label>
          <span>Chunk 大小</span>
          <input v-model.number="chunkSize" data-testid="chunk-size" type="number" min="50" max="10000" />
        </label>
        <label>
          <span>Overlap</span>
          <input v-model.number="chunkOverlap" data-testid="chunk-overlap" type="number" min="0" max="2000" />
        </label>
        <label>
          <span>分隔符</span>
          <input v-model="separatorsText" data-testid="chunk-separators" />
        </label>
        <label>
          <span>Token 上限</span>
          <input v-model.number="tokenLimit" data-testid="token-limit" type="number" min="0" max="8192" />
        </label>
        <label>
          <span>语言提示</span>
          <input v-model="languagesText" data-testid="chunk-languages" placeholder="zh,en" />
        </label>
        <label class="toggle-row">
          <span>Parent-Child</span>
          <input v-model="enableParentChild" data-testid="enable-parent-child" type="checkbox" />
        </label>
        <label>
          <span>Parent 大小</span>
          <input
            v-model.number="parentChunkSize"
            data-testid="parent-chunk-size"
            type="number"
            min="512"
            max="8192"
            :disabled="!enableParentChild"
          />
        </label>
        <label>
          <span>Child 大小</span>
          <input
            v-model.number="childChunkSize"
            data-testid="child-chunk-size"
            type="number"
            min="64"
            max="2048"
            :disabled="!enableParentChild"
          />
        </label>
      </div>
      <div class="preview-box">
        <label>
          <span>切分预览文本</span>
          <textarea v-model="previewSample" data-testid="preview-sample" rows="5"></textarea>
        </label>
        <button data-testid="preview-chunking" :disabled="previewing || !previewSample.trim()" @click="previewChunking">
          <Loader2 v-if="previewing" :size="17" class="spin" />
          <Play v-else :size="17" />
          切分预览
        </button>
      </div>
      <div v-if="previewResult" class="preview-result" data-testid="preview-result">
        <div>
          <strong>命中策略：{{ previewResult.selected_tier }}</strong>
          <span>切片 {{ previewResult.stats.count }} · 平均 {{ previewResult.stats.avg_chars }} 字 · 最大 {{ previewResult.stats.max_chars }} 字</span>
        </div>
        <div class="preview-profile">
          <span>标题 {{ previewResult.profile.md_heading_total }}</span>
          <span>页分隔 {{ previewResult.profile.form_feed_count }}</span>
          <span>章节标记 {{ previewResult.profile.chinese_chapter_count + previewResult.profile.english_chapter_count }}</span>
        </div>
        <article v-for="chunk in previewResult.chunks" :key="chunk.seq" class="preview-chunk">
          <strong>#{{ chunk.seq }} · {{ chunk.size_chars }} 字</strong>
          <small v-if="chunk.context_header">{{ chunk.context_header }}</small>
          <p>{{ chunk.content }}</p>
        </article>
      </div>
    </section>

    <section class="workspace">
      <aside class="panel control-panel">
        <div class="panel-title">
          <BookOpen :size="20" />
          <h2>知识库配置</h2>
        </div>
        <label>
          <span>名称</span>
          <input v-model="kbName" data-testid="kb-name" />
        </label>
        <label>
          <span>描述</span>
          <textarea v-model="kbDescription" data-testid="kb-description" rows="3"></textarea>
        </label>
        <button data-testid="create-kb" :disabled="busy" @click="createKnowledgeBase">
          <Loader2 v-if="busy" :size="17" class="spin" />
          <Play v-else :size="17" />
          创建知识库
        </button>

        <div v-if="knowledgeBase" class="object-block" data-testid="kb-result">
          <strong>{{ knowledgeBase.name }}</strong>
          <small>{{ knowledgeBase.id }}</small>
          <span>对话模型 {{ knowledgeBase.summary_model_id }}</span>
          <span>向量模型 {{ knowledgeBase.embedding_model_id }}</span>
          <span>{{ knowledgeBase.document_count }} 个文档 / {{ knowledgeBase.chunk_count }} 个切片</span>
          <button data-testid="reprocess-kb" :disabled="reprocessingKnowledgeBase" @click="reprocessCurrentKnowledgeBase">
            <Loader2 v-if="reprocessingKnowledgeBase" :size="16" class="spin" />
            <RefreshCcw v-else :size="16" />
            重建知识库
          </button>
        </div>

        <div class="panel-title upload-title">
          <UploadCloud :size="20" />
          <h2>文档上传</h2>
        </div>
        <label class="file-picker">
          <input
            class="native-file-input"
            data-testid="file-input"
            type="file"
            accept=".txt,.md,.pdf,.docx,.csv,.json,.xlsx"
            :disabled="uploading || polling"
            @change="handleFileSelected"
          />
          <span
            class="file-picker-button"
            data-testid="choose-file"
          >
            {{ selectedFile?.name || "选择文件" }}
          </span>
        </label>
        <small class="upload-hint">{{ uploadHint || "已选择文件，可以上传解析。" }}</small>
        <button
          data-testid="upload-doc"
          :disabled="uploading"
          @click="uploadDocument"
        >
          <Loader2 v-if="uploading || polling" :size="17" class="spin" />
          <UploadCloud v-else :size="17" />
          上传并解析
        </button>

        <div v-if="documentRecord" class="object-block" data-testid="doc-result">
          <strong>{{ documentRecord.title }}</strong>
          <small>{{ documentRecord.id }}</small>
          <span class="status" :class="documentRecord.parse_status">{{ statusText(documentRecord.parse_status) }}</span>
          <small v-if="documentRecord.error_message" class="inline-error">{{ documentRecord.error_message }}</small>
          <button data-testid="reprocess-doc" :disabled="reprocessingDocument" @click="reprocessCurrentDocument">
            <Loader2 v-if="reprocessingDocument" :size="16" class="spin" />
            <RefreshCcw v-else :size="16" />
            重新处理
          </button>
        </div>
      </aside>

      <section class="panel chunks-panel">
        <div class="panel-title">
          <FileText :size="20" />
          <h2>文档切片</h2>
        </div>
        <div v-if="chunks.length" class="chunk-list" data-testid="chunks-list">
          <article v-for="chunk in chunks" :key="chunk.id" class="chunk">
            <div>
              <strong>#{{ chunk.chunk_index }}</strong>
              <small>{{ chunk.chunk_type }} · {{ chunk.id }}</small>
            </div>
            <small v-if="chunk.context_header">{{ chunk.context_header }}</small>
            <p>{{ chunk.content }}</p>
          </article>
        </div>
        <div v-else class="empty">暂无切片</div>
      </section>

      <section class="panel answer-panel">
        <div class="panel-title">
          <MessageSquareText :size="20" />
          <h2>快速问答</h2>
        </div>
        <label>
          <span>问题</span>
          <textarea v-model="question" data-testid="question" rows="4"></textarea>
        </label>
        <button
          data-testid="ask-question"
          :disabled="!modelReady || !knowledgeBase || !question.trim() || answering"
          @click="askQuestion"
        >
          <Loader2 v-if="answering" :size="17" class="spin" />
          <Search v-else :size="17" />
          提问
        </button>

        <div class="knowledge-search" data-testid="knowledge-search-panel">
          <h3>知识搜索</h3>
          <label>
            <span>检索 Query</span>
            <input v-model="knowledgeSearchQuery" data-testid="knowledge-search-query" />
          </label>
          <button
            data-testid="run-knowledge-search"
            :disabled="!knowledgeBase || !knowledgeSearchQuery.trim() || searchingKnowledge"
            @click="searchKnowledge"
          >
            <Loader2 v-if="searchingKnowledge" :size="17" class="spin" />
            <Search v-else :size="17" />
            只检索来源
          </button>
          <div v-if="knowledgeSearchResult" class="search-results" data-testid="knowledge-search-result">
            <article v-for="hit in knowledgeSearchResult.hits" :key="hit.chunk_id" class="source">
              <strong>{{ hit.title || hit.document_id }}</strong>
              <small>
                {{ hit.retrieval_method || "unknown" }}
                · score {{ hit.score?.toFixed ? hit.score.toFixed(4) : hit.score }}
                {{ hit.vector_score ? " · vector " + hit.vector_score.toFixed(4) : "" }}
                {{ hit.keyword_score ? " · keyword " + hit.keyword_score.toFixed(4) : "" }}
                {{ hit.rrf_score ? " · rrf " + hit.rrf_score.toFixed(4) : "" }}
                {{ hit.rerank_score ? " · rerank " + hit.rerank_score.toFixed(4) : "" }}
              </small>
              <p>{{ hit.content }}</p>
            </article>
            <div v-if="!knowledgeSearchResult.hits.length" class="empty">没有命中来源</div>
          </div>
        </div>

        <div v-if="quickAnswer" class="answer" data-testid="answer-result">
          <h3>回答</h3>
          <p>{{ quickAnswer.answer }}</p>
          <h3>来源依据</h3>
          <article v-for="source in quickAnswer.sources" :key="source.chunk_id" class="source">
            <strong>{{ source.title || source.document_id }}</strong>
            <small>
              相似度 {{ source.score.toFixed(4) }}
              · {{ source.retrieval_method || "unknown" }}
              · {{ source.chunk_type || "text" }}
              {{ source.vector_score ? " · vector " + source.vector_score.toFixed(4) : "" }}
              {{ source.keyword_score ? " · keyword " + source.keyword_score.toFixed(4) : "" }}
              {{ source.rrf_score ? " · rrf " + source.rrf_score.toFixed(4) : "" }}
              {{ source.rerank_score ? " · rerank " + source.rerank_score.toFixed(4) : "" }}
              {{ source.context_chunk_id ? " · context " + source.context_chunk_id : "" }}
              {{ source.parent_chunk_id ? " · parent " + source.parent_chunk_id : "" }}
              {{ source.context_header ? " · " + source.context_header : "" }}
            </small>
            <p>{{ source.content }}</p>
          </article>
        </div>
      </section>
    </section>

    <footer class="logline">
      <span v-for="entry in eventLog" :key="entry">{{ entry }}</span>
    </footer>
  </main>
</template>
