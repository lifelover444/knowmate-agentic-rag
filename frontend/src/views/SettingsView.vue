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
  {
    name: "Local Storage",
    status: retrieval.runtimeStatus?.storage?.status === "ok" ? "已启用" : "不可用",
    description: String(retrieval.runtimeStatus?.storage?.path || "开发环境使用本地上传目录保存原始文件。"),
  },
  { name: "MinIO", status: "暂未启用", description: "S3-compatible 对象存储占位。" },
  { name: "S3", status: "暂未启用", description: "AWS S3 provider 占位。" },
  { name: "OSS", status: "暂未启用", description: "阿里云 OSS provider 占位。" },
  { name: "COS", status: "暂未启用", description: "腾讯云 COS provider 占位。" },
  { name: "OBS", status: "暂未启用", description: "华为云 OBS provider 占位。" },
]);

const systemStatusText = computed(() => retrieval.runtimeStatus?.system?.status || "unknown");

function selectSection(section: SettingsSection) {
  router.replace({ path: "/settings", query: { section } });
}

function parserDisplayName(name: string): string {
  if (name === "builtin") return "Builtin Parser";
  if (name === "ocr") return "MinerU OCR";
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
                <a-tag :color="engine.status === 'ok' ? 'green' : 'gray'">
                  {{ engine.status === 'ok' ? '已启用' : '暂未启用' }}
                </a-tag>
              </header>
              <p>{{ engine.description || engine.error_message }}</p>
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
                <a-tag :color="provider.status === '已启用' ? 'green' : 'gray'">{{ provider.status }}</a-tag>
              </header>
              <p>{{ provider.description }}</p>
            </article>
          </div>
        </section>
      </div>
    </section>
  </main>
</template>
