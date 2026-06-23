<script setup lang="ts">
import { Message } from "@arco-design/web-vue";
import { computed, onMounted, reactive } from "vue";
import { useParserConfigStore } from "../stores/parserConfig";
import { useRetrievalStore } from "../stores/retrieval";
import { formatApiError } from "../utils/api";

const parserConfig = useParserConfigStore();
const retrieval = useRetrievalStore();

const form = reactive({
  name: "MinerU",
  base_url: "https://mineru.net/api/v4",
  api_key: "",
  status: "active",
  model_version: "vlm",
  language: "ch",
  enable_table: true,
  enable_formula: true,
  is_ocr: false,
});

const mineruRuntime = computed(() =>
  (retrieval.runtimeStatus?.parser_engines || retrieval.parserEngines).find((engine) => engine.name === "mineru"),
);
const statusColor = computed(() => (mineruRuntime.value?.status === "ok" ? "green" : "gold"));
const statusText = computed(() => (mineruRuntime.value?.status === "ok" ? "已启用" : "未配置"));

function applyConfig() {
  const config = parserConfig.mineru;
  if (!config) return;
  form.name = config.name || "MinerU";
  form.base_url = config.base_url || "https://mineru.net/api/v4";
  form.status = config.status === "missing" ? "active" : config.status || "active";
  form.model_version = String(config.config.model_version || "vlm");
  form.language = String(config.config.language || "ch");
  form.enable_table = Boolean(config.config.enable_table ?? true);
  form.enable_formula = Boolean(config.config.enable_formula ?? true);
  form.is_ocr = Boolean(config.config.is_ocr ?? false);
}

async function saveMineru() {
  try {
    await parserConfig.saveMineruConfig({
      name: form.name,
      base_url: form.base_url,
      api_key: form.api_key.trim() || null,
      status: form.status,
      config: {
        model_version: form.model_version,
        language: form.language,
        enable_table: form.enable_table,
        enable_formula: form.enable_formula,
        is_ocr: form.is_ocr,
      },
    });
    form.api_key = "";
    await retrieval.loadRuntimeStatus();
    applyConfig();
    Message.success("MinerU 解析器配置已保存");
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

onMounted(async () => {
  try {
    await Promise.all([parserConfig.loadMineruConfig(), retrieval.loadRuntimeStatus()]);
    applyConfig();
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
});
</script>

<template>
  <main class="page-shell">
    <a-page-header title="解析器" subtitle="MinerU 用于 PDF、Office、图片等文档解析，文本类文件继续使用 builtin parser。" />

    <section class="content-card">
      <div class="section-heading">
        <div>
          <h2>MinerU 状态</h2>
          <p>API Key 只显示配置状态和尾号；文档上传解析会由后端转交 MinerU 标准 API。</p>
        </div>
        <a-tag :color="statusColor">{{ statusText }}</a-tag>
      </div>
      <div class="settings-status-grid">
        <article class="settings-status-card">
          <header>
            <strong>凭据</strong>
            <a-tag :color="parserConfig.mineru?.api_key_configured ? 'green' : 'gold'">
              {{ parserConfig.configuredText }}
            </a-tag>
          </header>
          <p>{{ mineruRuntime?.fix_suggestion || "MinerU 已可用于知识库文档解析。" }}</p>
        </article>
        <article class="settings-status-card">
          <header>
            <strong>默认模型</strong>
            <a-tag color="arcoblue">{{ form.model_version }}</a-tag>
          </header>
          <p>language={{ form.language }}，表格={{ form.enable_table ? "开" : "关" }}，公式={{ form.enable_formula ? "开" : "关" }}。</p>
        </article>
      </div>
    </section>

    <section class="content-card">
      <div class="section-heading">
        <div>
          <h2>MinerU 配置</h2>
          <p>留空 API Key 保存时会继续使用已保存 Key；首次保存必须填写。</p>
        </div>
      </div>
      <div class="form-grid">
        <a-form-item label="配置名称">
          <a-input v-model="form.name" data-testid="mineru-name" />
        </a-form-item>
        <a-form-item label="Base URL">
          <a-input v-model="form.base_url" data-testid="mineru-base-url" />
        </a-form-item>
        <a-form-item label="状态">
          <a-select v-model="form.status" data-testid="mineru-status">
            <a-option value="active">启用</a-option>
            <a-option value="disabled">停用</a-option>
          </a-select>
        </a-form-item>
        <a-form-item label="API Key">
          <a-input-password v-model="form.api_key" data-testid="mineru-api-key" placeholder="sk-..." allow-clear />
        </a-form-item>
        <a-form-item label="model_version">
          <a-select v-model="form.model_version" data-testid="mineru-model-version">
            <a-option value="vlm">vlm</a-option>
            <a-option value="pipeline">pipeline</a-option>
            <a-option value="MinerU-HTML">MinerU-HTML</a-option>
          </a-select>
        </a-form-item>
        <a-form-item label="language">
          <a-select v-model="form.language" data-testid="mineru-language">
            <a-option value="ch">ch</a-option>
            <a-option value="en">en</a-option>
            <a-option value="japan">japan</a-option>
            <a-option value="korean">korean</a-option>
            <a-option value="latin">latin</a-option>
          </a-select>
        </a-form-item>
        <a-form-item label="表格识别">
          <a-switch v-model="form.enable_table" data-testid="mineru-enable-table" />
        </a-form-item>
        <a-form-item label="公式识别">
          <a-switch v-model="form.enable_formula" data-testid="mineru-enable-formula" />
        </a-form-item>
        <a-form-item label="OCR">
          <a-switch v-model="form.is_ocr" data-testid="mineru-is-ocr" />
        </a-form-item>
      </div>
      <div class="actions-row">
        <a-button type="primary" data-testid="save-mineru-config" :loading="parserConfig.saving" @click="saveMineru">
          保存 MinerU 配置
        </a-button>
      </div>
    </section>
  </main>
</template>
