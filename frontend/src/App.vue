<script setup>
import {
  BookOpen,
  CheckCircle2,
  FileText,
  KeyRound,
  Loader2,
  MessageSquareText,
  Play,
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

const provider = ref("qwen");
const region = ref("cn");
const configName = ref("Qwen / DashScope");
const baseUrl = ref(qwenPresets.cn.baseUrl);
const apiKey = ref("");
const apiKeyLast4 = ref("");
const apiKeyConfigured = ref(false);
const chatModel = ref(qwenPresets.cn.chatModel);
const embeddingModel = ref(qwenPresets.cn.embeddingModel);
const embeddingDimension = ref(qwenPresets.cn.embeddingDimension);
const modelReady = ref(false);
const testingModel = ref(false);
const savingModel = ref(false);
const modelTestResult = ref(null);
const applyingSavedConfig = ref(false);

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
const busy = ref(false);
const uploading = ref(false);
const polling = ref(false);
const answering = ref(false);
const errorMessage = ref("");
const eventLog = ref([]);

const apiKeyHint = computed(() => {
  if (apiKeyConfigured.value && apiKeyLast4.value) {
    return `已配置，尾号 ****${apiKeyLast4.value}。留空保存将继续使用旧 Key。`;
  }
  return "请输入模型服务 API Key，保存后后端加密存储。";
});

const uploadHint = computed(() => {
  if (!modelReady.value) return "请先完成模型配置并测试通过。";
  if (!knowledgeBase.value) return "请先创建知识库。";
  if (!selectedFile.value) return "请选择要上传的文档。";
  return "";
});

const pipeline = computed(() => [
  { label: "模型配置", done: modelReady.value, active: testingModel.value || savingModel.value },
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

watch([provider, region], () => {
  if (applyingSavedConfig.value) return;
  if (provider.value !== "qwen") return;
  const preset = qwenPresets[region.value];
  configName.value = "Qwen / DashScope";
  baseUrl.value = preset.baseUrl;
  chatModel.value = preset.chatModel;
  embeddingModel.value = preset.embeddingModel;
  embeddingDimension.value = preset.embeddingDimension;
  modelReady.value = false;
  modelTestResult.value = null;
});

watch([baseUrl, apiKey, chatModel, embeddingModel, embeddingDimension], () => {
  if (applyingSavedConfig.value) return;
  modelReady.value = false;
  modelTestResult.value = null;
});

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

function modelPayload(includeEmptyKey = false) {
  return {
    provider: provider.value,
    name: configName.value.trim() || (provider.value === "qwen" ? "Qwen / DashScope" : "OpenAI Compatible"),
    base_url: baseUrl.value.trim(),
    api_key: apiKey.value.trim() || (includeEmptyKey ? "" : undefined),
    chat_model: chatModel.value.trim(),
    embedding_model: embeddingModel.value.trim(),
    embedding_dimension: Number(embeddingDimension.value),
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
  provider.value = config.provider;
  configName.value = config.name;
  baseUrl.value = config.base_url;
  chatModel.value = config.chat_model;
  embeddingModel.value = config.embedding_model;
  embeddingDimension.value = config.embedding_dimension;
  apiKeyConfigured.value = config.api_key_configured;
  apiKeyLast4.value = config.api_key_last4 || "";
  apiKey.value = "";
  modelReady.value = config.api_key_configured;
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

async function loadParserEngines() {
  try {
    parserEngines.value = await request("/parser-engines");
  } catch (error) {
    handleError(error);
  }
}

async function testModelConfig() {
  testingModel.value = true;
  errorMessage.value = "";
  modelReady.value = false;
  try {
    modelTestResult.value = await jsonRequest("/model-config/test", "POST", modelPayload(true));
    modelReady.value = modelTestResult.value.chat_ok && modelTestResult.value.embedding_ok;
    log(modelReady.value ? "模型连接测试通过" : "模型连接测试未通过");
  } catch (error) {
    modelTestResult.value = null;
    handleError(error);
  } finally {
    testingModel.value = false;
  }
}

async function saveModelConfig() {
  savingModel.value = true;
  errorMessage.value = "";
  try {
    const config = await jsonRequest("/model-config", "PUT", modelPayload(true));
    applySavedConfig(config);
    modelReady.value = true;
    log("模型配置已保存");
  } catch (error) {
    handleError(error);
  } finally {
    savingModel.value = false;
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
      top_k: 5,
    });
    log(`返回来源 ${quickAnswer.value.sources.length}`);
  } catch (error) {
    handleError(error);
  } finally {
    answering.value = false;
  }
}

onMounted(() => {
  loadModelConfig();
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
      <div class="model-grid">
        <label>
          <span>供应商</span>
          <select v-model="provider" data-testid="provider">
            <option value="qwen">Qwen / DashScope</option>
            <option value="openai-compatible">OpenAI 兼容</option>
          </select>
        </label>
        <label>
          <span>区域</span>
          <select v-model="region" data-testid="region" :disabled="provider !== 'qwen'">
            <option value="cn">中国内地</option>
            <option value="intl">国际站</option>
          </select>
        </label>
        <label>
          <span>配置名称</span>
          <input v-model="configName" data-testid="config-name" />
        </label>
        <label>
          <span>Base URL</span>
          <input v-model="baseUrl" data-testid="base-url" />
        </label>
        <label>
          <span>API Key</span>
          <input v-model="apiKey" data-testid="api-key" type="password" autocomplete="off" />
          <small>{{ apiKeyHint }}</small>
        </label>
        <label>
          <span>对话模型</span>
          <input v-model="chatModel" data-testid="chat-model" />
        </label>
        <label>
          <span>向量模型</span>
          <input v-model="embeddingModel" data-testid="embedding-model" />
        </label>
        <label>
          <span>向量维度</span>
          <input v-model.number="embeddingDimension" data-testid="embedding-dimension" type="number" min="1" />
        </label>
      </div>
      <div class="model-actions">
        <button data-testid="test-model" :disabled="testingModel" @click="testModelConfig">
          <Loader2 v-if="testingModel" :size="17" class="spin" />
          <KeyRound v-else :size="17" />
          测试连接
        </button>
        <button data-testid="save-model" :disabled="savingModel || !modelReady" @click="saveModelConfig">
          <Loader2 v-if="savingModel" :size="17" class="spin" />
          <Save v-else :size="17" />
          保存配置
        </button>
      </div>
      <p v-if="modelTestResult" class="model-result" :class="{ ok: modelReady }" data-testid="model-test-result">
        {{ modelTestResult.message }}；对话 {{ modelTestResult.chat_ok ? "正常" : "异常" }}，向量
        {{ modelTestResult.embedding_ok ? "正常" : "异常" }}，检测维度
        {{ modelTestResult.detected_dimension || "-" }}
      </p>
      <p class="model-note">切换向量模型或维度后，已有文档不会自动重建向量；建议新建知识库或重新上传文档。</p>
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
          <span>{{ knowledgeBase.document_count }} 个文档 / {{ knowledgeBase.chunk_count }} 个切片</span>
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

        <div v-if="quickAnswer" class="answer" data-testid="answer-result">
          <h3>回答</h3>
          <p>{{ quickAnswer.answer }}</p>
          <h3>来源依据</h3>
          <article v-for="source in quickAnswer.sources" :key="source.chunk_id" class="source">
            <strong>{{ source.title || source.document_id }}</strong>
            <small>相似度 {{ source.score.toFixed(4) }}{{ source.context_header ? " · " + source.context_header : "" }}</small>
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
