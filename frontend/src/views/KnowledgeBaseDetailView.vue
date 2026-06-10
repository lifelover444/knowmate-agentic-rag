<script setup lang="ts">
import { Message } from "@arco-design/web-vue";
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import DocumentsView from "./DocumentsView.vue";
import FAQView from "./FAQView.vue";
import { useKnowledgeBaseStore } from "../stores/knowledgeBase";
import { useModelsStore } from "../stores/models";
import { useRetrievalStore } from "../stores/retrieval";
import type { ChunkingConfig, FAQConfig, IndexingStrategy, ParserEngineRule } from "../types/api";
import { formatApiError } from "../utils/api";

type DetailSection = "overview" | "documents" | "faqs" | "settings" | "tasks";

const route = useRoute();
const router = useRouter();
const kbStore = useKnowledgeBaseStore();
const modelStore = useModelsStore();
const retrieval = useRetrievalStore();
const kbId = computed(() => String(route.params.kbId || ""));
const activeSection = ref<DetailSection>("overview");
const settingsSaving = ref(false);
const reindexNotice = ref(false);

const settingsForm = reactive({
  name: "",
  description: "",
  kb_type: "document",
  summary_model_id: "",
  embedding_model_id: "",
  parserRulesText: "",
  chunkStrategy: "auto",
  chunkSize: 512,
  chunkOverlap: 80,
  separatorsText: "\\n\\n,\\n,。",
  tokenLimit: 0,
  languagesText: "",
  enableParentChild: true,
  enableRerank: true,
  faqIndexMode: "question_answer",
  faqQuestionIndexMode: "combined",
});

const currentKb = computed(() => kbStore.currentKb);
// document KB 默认展示文档管理；FAQ KB 默认展示 FAQ 管理。
const defaultSection = computed<DetailSection>(() => (currentKb.value?.kb_type === "faq" ? "faqs" : "documents"));
const capabilities = computed(() => currentKb.value?.capabilities);

const sectionTabs = computed(() => [
  { key: "overview", label: "概览", enabled: true },
  { key: "documents", label: "文档管理", enabled: capabilities.value?.document !== false },
  { key: "faqs", label: "FAQ 管理", enabled: capabilities.value?.faq !== false },
  { key: "settings", label: "设置", enabled: true },
  { key: "tasks", label: "任务/状态", enabled: true },
  { key: "wiki", label: "Wiki 未启用", enabled: false },
  { key: "graph", label: "Graph 未启用", enabled: false },
]);

function normalizeSection(value: unknown): DetailSection {
  const section = String(value || "");
  if (["overview", "documents", "faqs", "settings", "tasks"].includes(section)) {
    return section as DetailSection;
  }
  return defaultSection.value;
}

function parseList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.replaceAll("\\n", "\n").trim())
    .filter(Boolean);
}

function parserRulesText(rules?: ParserEngineRule[] | null): string {
  return (rules || [])
    .map((rule) => `${rule.file_types.join(",")}:${rule.engine}`)
    .join("\n");
}

function parseParserRules(value: string): ParserEngineRule[] {
  const rules = value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [fileTypesText, engine] = line.split(":");
      const fileTypes = parseList(fileTypesText || "");
      if (!fileTypes.length || !engine?.trim()) {
        throw new Error("parser rules 必须使用 pdf,txt:builtin 格式");
      }
      return { file_types: fileTypes, engine: engine.trim() };
    });
  return rules.length ? rules : retrieval.parserEngineRulesPayload();
}

function syncSettingsForm() {
  if (!currentKb.value) return;
  settingsForm.name = currentKb.value.name;
  settingsForm.description = currentKb.value.description || "";
  settingsForm.kb_type = currentKb.value.kb_type || "document";
  settingsForm.summary_model_id = currentKb.value.summary_model_id;
  settingsForm.embedding_model_id = currentKb.value.embedding_model_id;
  settingsForm.parserRulesText = parserRulesText(currentKb.value.parser_engine_rules as ParserEngineRule[] | null);
  settingsForm.chunkStrategy = "auto";
  settingsForm.chunkSize = 512;
  settingsForm.chunkOverlap = 80;
  settingsForm.separatorsText = "\\n\\n,\\n,。";
  settingsForm.tokenLimit = 0;
  settingsForm.languagesText = "";
  settingsForm.enableParentChild = true;
  settingsForm.enableRerank = true;
  const faqConfig = (currentKb.value.faq_config || {}) as FAQConfig;
  settingsForm.faqIndexMode = String(faqConfig.index_mode || "question_answer");
  settingsForm.faqQuestionIndexMode = String(faqConfig.question_index_mode || "combined");
}

function validateSettingsModels() {
  if (!modelStore.chatModels.some((model) => model.id === settingsForm.summary_model_id)) {
    throw new Error("QA 模型必须选择 KnowledgeQA 类型");
  }
  if (!modelStore.embeddingModels.some((model) => model.id === settingsForm.embedding_model_id)) {
    throw new Error("Embedding 模型必须选择 Embedding 类型");
  }
}

function settingsChunkingPayload(): ChunkingConfig {
  return {
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
}

function settingsIndexingStrategyPayload(): IndexingStrategy {
  return {
    enable_vector: true,
    enable_keyword: true,
    enable_parent_child: true,
    enable_rerank: true,
    enable_wiki: false,
    enable_knowledge_graph: false,
  };
}

function switchSection(key: string, enabled: boolean) {
  if (!enabled) {
    Message.info("未实现能力暂不可进入");
    return;
  }
  const section = normalizeSection(key);
  activeSection.value = section;
  router.replace({ query: { ...route.query, section } });
}

async function loadDetail() {
  await Promise.all([
    kbStore.loadKnowledgeBase(kbId.value),
    kbStore.loadTasks({ knowledge_base_id: kbId.value }),
    modelStore.loadModels(),
    retrieval.loadParserEngines(),
  ]);
  activeSection.value = normalizeSection(route.query.section);
  syncSettingsForm();
}

async function submitSettings() {
  settingsSaving.value = true;
  try {
    validateSettingsModels();
    await kbStore.updateKnowledgeBase(kbId.value, {
      name: settingsForm.name,
      description: settingsForm.description,
      kb_type: settingsForm.kb_type,
      summary_model_id: settingsForm.summary_model_id,
      embedding_model_id: settingsForm.embedding_model_id,
      vector_store_id: null,
      faq_config: settingsForm.kb_type === "faq"
        ? {
          index_mode: settingsForm.faqIndexMode,
          question_index_mode: settingsForm.faqQuestionIndexMode,
        }
        : null,
      parser_engine_rules: parseParserRules(settingsForm.parserRulesText),
      chunking_config: settingsChunkingPayload(),
      indexing_strategy: settingsIndexingStrategyPayload(),
    });
    reindexNotice.value = true;
    Message.success("配置已保存，需要重处理/重建索引后对已有文档生效");
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  } finally {
    settingsSaving.value = false;
  }
}

async function rebuildFromSettings() {
  try {
    await kbStore.reprocessKnowledgeBase(kbId.value);
    Message.success("已提交重建索引");
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

onMounted(() => {
  loadDetail().catch((error) => {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  });
});

watch(
  () => route.query.section,
  (section) => {
    activeSection.value = normalizeSection(section);
  },
);

watch(defaultSection, (section) => {
  if (!route.query.section) activeSection.value = section;
});

watch(currentKb, syncSettingsForm);
</script>

<template>
  <main class="page-shell kb-detail-shell">
    <a-page-header
      :title="currentKb?.name || 'WeKnora-like KB 详情'"
      :subtitle="currentKb?.description || '以知识库为中心管理文档、FAQ、设置和处理状态。'"
      @back="router.push('/knowledge-bases')"
    >
      <template #extra>
        <a-space>
          <a-button @click="router.push(`/knowledge-bases/${kbId}/documents`)">打开旧文档页</a-button>
          <a-button @click="router.push(`/knowledge-bases/${kbId}/faqs`)">打开旧 FAQ 页</a-button>
        </a-space>
      </template>
    </a-page-header>

    <section class="content-card kb-detail-overview">
      <div class="kb-detail-metrics">
        <span>文档 {{ currentKb?.document_count || 0 }}</span>
        <span>chunks {{ currentKb?.chunk_count || 0 }}</span>
        <span>处理中 {{ currentKb?.processing_count || 0 }}</span>
        <span>{{ currentKb?.kb_type === "faq" ? "FAQ 知识库" : "文档知识库" }}</span>
      </div>
      <div class="kb-detail-tabs" data-testid="kb-detail-tabs">
        <a-button
          v-for="tab in sectionTabs"
          :key="tab.key"
          size="small"
          :type="activeSection === tab.key ? 'primary' : 'secondary'"
          :disabled="!tab.enabled"
          @click="switchSection(tab.key, tab.enabled)"
        >
          {{ tab.label }}
        </a-button>
      </div>
    </section>

    <section v-if="activeSection === 'overview'" class="content-card kb-detail-panel">
      <div class="section-heading">
        <div>
          <h2>概览</h2>
          <p>WeKnora-like KB 详情把入口收敛到单个知识库页面，当前版本复用现有文档和 FAQ 工作流。</p>
        </div>
        <a-tag :color="currentKb?.is_pinned ? 'gold' : 'gray'">{{ currentKb?.is_pinned ? "已置顶" : "未置顶" }}</a-tag>
      </div>
      <a-descriptions :column="2" bordered>
        <a-descriptions-item label="Embedding 模型">{{ currentKb?.embedding_model_id }}</a-descriptions-item>
        <a-descriptions-item label="QA 模型">{{ currentKb?.summary_model_id }}</a-descriptions-item>
        <a-descriptions-item label="向量">{{ capabilities?.vector ? "启用" : "未启用" }}</a-descriptions-item>
        <a-descriptions-item label="关键词">{{ capabilities?.keyword ? "启用" : "未启用" }}</a-descriptions-item>
        <a-descriptions-item label="父子块">{{ capabilities?.parent_child ? "启用" : "未启用" }}</a-descriptions-item>
        <a-descriptions-item label="重排">{{ capabilities?.rerank ? "启用" : "未启用" }}</a-descriptions-item>
      </a-descriptions>
    </section>

    <DocumentsView v-if="activeSection === 'documents'" class="kb-detail-embedded" />
    <FAQView v-if="activeSection === 'faqs'" class="kb-detail-embedded" />

    <section v-if="activeSection === 'settings'" class="content-card kb-detail-panel">
      <div class="section-heading">
        <div>
          <h2>设置</h2>
          <p>KBModelConfig / KBParserSettings / KBChunkingSettings / KBIndexingStrategy 的轻量复刻，保存后需要重处理/重建索引。</p>
        </div>
        <a-space>
          <a-button @click="router.push('/settings')">打开全局设置</a-button>
          <a-button type="primary" :loading="settingsSaving" @click="submitSettings">保存设置</a-button>
        </a-space>
      </div>
      <a-alert
        v-if="reindexNotice"
        type="warning"
        content="配置已保存，需要重处理/重建索引后对已有文档生效"
      />
      <div class="kb-settings-form">
        <section>
          <h3>基础信息</h3>
          <div class="form-grid form-grid--compact">
            <a-form-item label="名称">
              <a-input v-model="settingsForm.name" />
            </a-form-item>
            <a-form-item label="知识库类型">
              <a-radio-group v-model="settingsForm.kb_type" type="button">
                <a-radio value="document">文档知识库</a-radio>
                <a-radio value="faq">FAQ 知识库</a-radio>
              </a-radio-group>
            </a-form-item>
            <a-form-item label="描述">
              <a-textarea v-model="settingsForm.description" :auto-size="{ minRows: 2, maxRows: 4 }" />
            </a-form-item>
            <a-form-item label="vector store">
              <a-tag color="blue">VectorStore：默认 Qdrant</a-tag>
            </a-form-item>
          </div>
        </section>

        <section>
          <h3>模型配置</h3>
          <div class="form-grid form-grid--compact">
            <a-form-item label="QA 模型">
              <a-select v-model="settingsForm.summary_model_id" placeholder="QA 模型必须选择 KnowledgeQA 类型">
                <a-option v-for="model in modelStore.chatModels" :key="model.id" :value="model.id">
                  {{ model.name }} · {{ model.model_name }}
                </a-option>
              </a-select>
            </a-form-item>
            <a-form-item label="Embedding 模型">
              <a-select v-model="settingsForm.embedding_model_id" placeholder="Embedding 模型必须选择 Embedding 类型">
                <a-option v-for="model in modelStore.embeddingModels" :key="model.id" :value="model.id">
                  {{ model.name }} · {{ model.model_name }}
                </a-option>
              </a-select>
            </a-form-item>
          </div>
        </section>

        <section v-if="settingsForm.kb_type === 'faq'" class="faq-config-panel">
          <h3>FAQ index mode</h3>
          <div class="form-grid form-grid--compact">
            <a-form-item label="索引内容">
              <a-radio-group v-model="settingsForm.faqIndexMode" type="button">
                <a-radio value="question_only">question_only</a-radio>
                <a-radio value="question_answer">question_answer</a-radio>
              </a-radio-group>
            </a-form-item>
            <a-form-item label="问法索引">
              <a-radio-group v-model="settingsForm.faqQuestionIndexMode" type="button">
                <a-radio value="combined">combined</a-radio>
                <a-radio value="separate">separate</a-radio>
              </a-radio-group>
            </a-form-item>
          </div>
          <p class="muted-text">
            question_only 仅索引标准问和相似问；question_answer 会把答案一起索引。
            combined 合并标准问和相似问；separate 为每个问法建立独立索引。
          </p>
        </section>

        <section>
          <h3>parser rules</h3>
          <a-textarea
            v-model="settingsForm.parserRulesText"
            placeholder="pdf,txt:builtin"
            :auto-size="{ minRows: 3, maxRows: 6 }"
          />
          <p class="muted-text">每行一个规则，例如 pdf,txt:builtin。可用 parser 来自 `/parser-engines`。</p>
        </section>

        <section>
          <h3>chunking config · 切分配置：只读展示</h3>
          <div class="form-grid form-grid--compact">
            <a-form-item label="策略">
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
            <a-form-item label="parent-child">
              <a-tag color="green">true</a-tag>
            </a-form-item>
            <a-form-item label="parent size">
              <a-tag>4096</a-tag>
            </a-form-item>
            <a-form-item label="child size">
              <a-tag>384</a-tag>
            </a-form-item>
          </div>
        </section>

        <section>
          <h3>indexing strategy</h3>
          <div class="form-grid form-grid--compact">
            <a-form-item label="vector">
              <a-tag color="green">vector 固定开启</a-tag>
            </a-form-item>
            <a-form-item label="keyword">
              <a-tag color="green">keyword 固定开启</a-tag>
            </a-form-item>
            <a-form-item label="parent-child">
              <a-tag color="green">parent-child 固定开启 · v0.9 固定启用</a-tag>
            </a-form-item>
            <a-form-item label="rerank">
              <a-tag color="green">rerank 固定开启 · v0.9 固定启用</a-tag>
            </a-form-item>
            <a-form-item label="Wiki">
              <a-tag color="gray">Wiki 关闭 · Wiki 暂未实现</a-tag>
            </a-form-item>
            <a-form-item label="Knowledge Graph">
              <a-tag color="gray">Knowledge Graph 关闭 · Graph 暂未实现</a-tag>
            </a-form-item>
          </div>
        </section>

        <div class="actions-row">
          <a-space>
            <a-button @click="rebuildFromSettings">立即重建索引</a-button>
            <a-button type="primary" :loading="settingsSaving" @click="submitSettings">保存设置</a-button>
          </a-space>
        </div>
      </div>
    </section>

    <section v-if="activeSection === 'tasks'" class="content-card kb-detail-panel">
      <div class="section-heading">
        <div>
          <h2>任务/状态</h2>
          <p>展示当前知识库的处理任务和解析状态，后续 TASK-016/TASK-017 会补齐阶段 timeline。</p>
        </div>
        <a-button size="small" @click="loadDetail">刷新</a-button>
      </div>
      <a-empty v-if="!kbStore.tasks.length" description="暂无处理任务" />
      <div v-else class="task-list">
        <div v-for="task in kbStore.tasks" :key="task.id" class="task-list-item">
          <header>
            <strong>{{ task.task_type }}</strong>
            <a-tag :color="task.status === 'failed' ? 'red' : task.status === 'completed' ? 'green' : 'blue'">
              {{ task.status }}
            </a-tag>
          </header>
          <span>进度 {{ task.progress }}%</span>
          <small v-if="task.error_message">{{ task.error_message }}</small>
        </div>
      </div>
    </section>
  </main>
</template>
