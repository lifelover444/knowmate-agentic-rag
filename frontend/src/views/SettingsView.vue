<script setup lang="ts">
import { computed, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import ModelSettingsView from "./ModelSettingsView.vue";
import RetrievalSettingsView from "./RetrievalSettingsView.vue";
import VectorStoreSettingsView from "./VectorStoreSettingsView.vue";
import { useRetrievalStore } from "../stores/retrieval";

type SettingsSection = "models" | "vector-stores" | "retrieval" | "parser" | "storage";

const route = useRoute();
const router = useRouter();
const retrieval = useRetrievalStore();

const settingsGroups = [
  {
    key: "models_runtime",
    title: "模型与运行时",
    items: [
      { key: "models", title: "模型配置", description: "OpenAI-compatible chat、embedding、rerank 配置" },
      { key: "vector-stores", title: "向量库", description: "Qdrant 连接与集合状态" },
      { key: "retrieval", title: "检索与分块", description: "召回、重排、chunk 策略和父子块" },
    ],
  },
  {
    key: "data_extensions",
    title: "数据扩展",
    items: [
      { key: "parser", title: "解析器", description: "按文件类型选择解析引擎" },
      { key: "storage", title: "存储", description: "文件存储 provider 可见状态" },
    ],
  },
] as const;

const componentMap = {
  models: ModelSettingsView,
  "vector-stores": VectorStoreSettingsView,
  retrieval: RetrievalSettingsView,
} as const;

const activeSection = computed<SettingsSection>(() => {
  const section = String(route.query.section || "models");
  if (["models", "vector-stores", "retrieval", "parser", "storage"].includes(section)) {
    return section as SettingsSection;
  }
  return "models";
});

const activeComponent = computed(() => {
  if (activeSection.value in componentMap) {
    return componentMap[activeSection.value as keyof typeof componentMap];
  }
  return undefined;
});

const parserEngines = computed(() => retrieval.runtimeStatus?.parser_engines || retrieval.parserEngines);

const storageProviders = computed(() => [
  ...(
    retrieval.runtimeStatus?.storage_providers || [
      {
        provider: "local",
        label: "Local Storage",
        status: "ok",
        description: "开发环境使用本地上传目录保存原始文件。",
      },
      { provider: "minio", label: "MinIO", status: "planned", description: "MinIO 对象存储 provider 暂未启用。" },
      { provider: "s3", label: "S3", status: "planned", description: "S3 对象存储 provider 占位。" },
      { provider: "oss", label: "OSS", status: "planned", description: "OSS 对象存储 provider 占位。" },
      { provider: "cos", label: "COS", status: "planned", description: "COS 对象存储 provider 占位。" },
      { provider: "obs", label: "OBS", status: "planned", description: "OBS 对象存储 provider 占位。" },
    ]
  ).map((provider) => ({
    name: provider.label || provider.provider,
    status: statusText(provider.status),
    rawStatus: provider.status,
    description: provider.path || provider.description || provider.fix_suggestion || "对象存储 provider 占位。",
  })),
]);

const systemStatusText = computed(() => retrieval.runtimeStatus?.system?.status || "unknown");
const modelRuntimeStatus = computed(() => retrieval.runtimeStatus?.model_configs);
const vectorStoreRuntimeStatus = computed(() => retrieval.runtimeStatus?.vector_stores);
const fixSuggestions = computed(() => retrieval.runtimeStatus?.fix_suggestions || []);
const requiredModelTypes = computed(() =>
  Object.entries(modelRuntimeStatus.value?.required_types || {}).map(([type, item]) => ({ type, ...item })),
);

function selectSection(section: SettingsSection) {
  router.replace({ path: "/settings", query: { section } });
}

function statusText(status: string | undefined): string {
  if (status === "ok") return "已启用";
  if (status === "planned") return "计划接入";
  if (status === "missing") return "未配置";
  if (status === "error") return "异常";
  return status || "未知";
}

function statusColor(status: string | undefined): string {
  if (status === "ok") return "green";
  if (status === "planned") return "orange";
  if (status === "missing") return "gold";
  if (status === "error") return "red";
  return "gray";
}

function parserDisplayName(name: string): string {
  if (name === "builtin") return "Builtin Parser";
  if (name === "ocr") return "MinerU OCR";
  if (name === "mineru") return "MinerU";
  if (name === "docreader") return "DocReader";
  return name || "Local Parser Registry";
}

onMounted(() => {
  retrieval.loadRuntimeStatus().catch(() => undefined);
});
</script>

<template>
  <main class="page-shell settings-shell">
    <section class="content-card settings-hero">
      <div>
        <h1>设置中心</h1>
        <p>按 WeKnora 的配置组织方式集中管理模型、向量库、检索、解析器和存储状态。</p>
      </div>
    </section>

    <section class="settings-layout">
      <aside class="content-card settings-nav">
        <div v-for="group in settingsGroups" :key="group.key" class="settings-nav__group">
          <strong>{{ group.title }}</strong>
          <button
            v-for="item in group.items"
            :key="item.key"
            type="button"
            :class="{ active: activeSection === item.key }"
            @click="selectSection(item.key)"
          >
            <span>{{ item.title }}</span>
            <small>{{ item.description }}</small>
          </button>
        </div>
      </aside>

      <div class="settings-content">
        <section class="content-card runtime-summary-panel">
          <div class="section-heading">
            <div>
              <h2>运行状态</h2>
              <p>系统状态：{{ systemStatusText }}。模型、向量库、数据库、解析器和对象存储状态来自后端运行检查。</p>
            </div>
          </div>
          <div class="settings-status-grid">
            <article class="settings-status-card model-runtime-status">
              <header>
                <strong>模型配置</strong>
                <a-tag :color="modelRuntimeStatus?.summary?.total ? 'green' : 'gold'">
                  {{ modelRuntimeStatus?.summary?.total || 0 }} 个模型
                </a-tag>
              </header>
              <p>
                API Key 已配置 {{ modelRuntimeStatus?.summary?.api_key_configured || 0 }} 个；Rerank 缺失时仍可使用非重排 Quick Q&A。
              </p>
              <div class="runtime-chip-row">
                <a-tag
                  v-for="model in requiredModelTypes"
                  :key="model.type"
                  :color="statusColor(model.status)"
                >
                  {{ model.type }} · {{ statusText(model.status) }}
                </a-tag>
              </div>
            </article>

            <article class="settings-status-card vector-store-runtime-status">
              <header>
                <strong>VectorStore</strong>
                <a-tag :color="statusColor(String(retrieval.runtimeStatus?.vector_store?.status || 'unknown'))">
                  {{ statusText(String(retrieval.runtimeStatus?.vector_store?.status || 'unknown')) }}
                </a-tag>
              </header>
              <p>
                默认 {{ String(vectorStoreRuntimeStatus?.default?.provider || 'qdrant') }}；已注册
                {{ vectorStoreRuntimeStatus?.registered_count || 0 }} 个配置。
              </p>
            </article>
          </div>

          <div v-if="fixSuggestions.length" class="runtime-fix-suggestions">
            <strong>修复建议</strong>
            <ul>
              <li v-for="suggestion in fixSuggestions" :key="suggestion">{{ suggestion }}</li>
            </ul>
          </div>
        </section>

        <component :is="activeComponent" v-if="activeComponent" />

        <section v-else-if="activeSection === 'parser'" class="content-card settings-status-panel parser-engine-status">
          <div class="section-heading">
            <div>
              <h2>解析器</h2>
              <p>系统状态：{{ systemStatusText }}。当前 parser_engine_status 来自后端运行状态。</p>
            </div>
          </div>
          <div class="settings-status-grid">
            <article v-for="engine in parserEngines" :key="engine.name" class="settings-status-card">
              <header>
                <strong>{{ parserDisplayName(engine.name) }}</strong>
                <a-tag :color="statusColor(engine.status)">
                  {{ statusText(engine.status) }}
                </a-tag>
              </header>
              <p>{{ engine.description || engine.error_message || engine.fix_suggestion }}</p>
            </article>
          </div>
        </section>

        <section v-else class="content-card settings-status-panel storage-provider-status">
          <div class="section-heading">
            <div>
              <h2>存储</h2>
              <p>系统状态：{{ systemStatusText }}。Local storage、向量库和数据库状态来自后端运行检查。</p>
            </div>
          </div>
          <div class="settings-status-grid">
            <article v-for="provider in storageProviders" :key="provider.name" class="settings-status-card">
              <header>
                <strong>{{ provider.name }}</strong>
                <a-tag :color="statusColor(provider.rawStatus)">{{ provider.status }}</a-tag>
              </header>
              <p>{{ provider.description }}</p>
            </article>
          </div>
        </section>
      </div>
    </section>
  </main>
</template>
