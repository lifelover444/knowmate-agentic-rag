<script setup lang="ts">
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import ModelSettingsView from "./ModelSettingsView.vue";
import RetrievalSettingsView from "./RetrievalSettingsView.vue";
import VectorStoreSettingsView from "./VectorStoreSettingsView.vue";

type SettingsSection = "models" | "vector-stores" | "retrieval" | "parser" | "storage";

const route = useRoute();
const router = useRouter();

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

const parserEngines = [
  {
    name: "Builtin Parser",
    status: "已启用",
    description: "当前默认本地解析链路，覆盖 txt、markdown、csv、pdf/docx 基础文本抽取。",
  },
  {
    name: "Local Parser Registry",
    status: "已启用",
    description: "由检索与分块配置选择 parser_engine，按知识库规则参与文档处理。",
  },
  {
    name: "MinerU OCR",
    status: "暂未启用",
    description: "保留 WeKnora-style 高级 PDF/OCR provider 占位，未接入前不要求凭证。",
  },
];

const storageProviders = [
  { name: "Local Storage", status: "已启用", description: "开发环境使用本地上传目录保存原始文件。" },
  { name: "MinIO", status: "暂未启用", description: "S3-compatible 对象存储占位。" },
  { name: "S3", status: "暂未启用", description: "AWS S3 provider 占位。" },
  { name: "OSS", status: "暂未启用", description: "阿里云 OSS provider 占位。" },
  { name: "COS", status: "暂未启用", description: "腾讯云 COS provider 占位。" },
  { name: "OBS", status: "暂未启用", description: "华为云 OBS provider 占位。" },
];

function selectSection(section: SettingsSection) {
  router.replace({ path: "/settings", query: { section } });
}
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
              <p>当前先暴露 builtin/local 状态，后续再按 provider 接入 MinerU/OCR。</p>
            </div>
          </div>
          <div class="settings-status-grid">
            <article v-for="engine in parserEngines" :key="engine.name" class="settings-status-card">
              <header>
                <strong>{{ engine.name }}</strong>
                <a-tag :color="engine.status === '已启用' ? 'green' : 'gray'">{{ engine.status }}</a-tag>
              </header>
              <p>{{ engine.description }}</p>
            </article>
          </div>
        </section>

        <section v-else class="content-card settings-status-panel storage-provider-status">
          <div class="section-heading">
            <div>
              <h2>存储</h2>
              <p>只展示当前 local storage 和对象存储 provider 占位，不提前保存未实现 provider 凭证。</p>
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
