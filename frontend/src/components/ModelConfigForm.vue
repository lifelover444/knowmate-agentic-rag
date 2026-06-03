<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import type { ModelPayload, ModelProviderPreset, ModelRead, ModelTestPayload, ModelType } from "../types/api";

const qwenPresets = {
  cn: {
    baseUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    chatModel: "qwen-plus",
    embeddingModel: "text-embedding-v4",
    rerankBaseUrl: "https://dashscope.aliyuncs.com/compatible-api/v1/reranks",
    rerankModel: "qwen3-rerank",
    embeddingDimension: 1024,
  },
  intl: {
    baseUrl: "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    chatModel: "qwen-plus",
    embeddingModel: "text-embedding-v4",
    rerankBaseUrl: "https://dashscope-intl.aliyuncs.com/compatible-api/v1/reranks",
    rerankModel: "qwen3-rerank",
    embeddingDimension: 1024,
  },
};

const deepseekPreset = {
  baseUrl: "https://api.deepseek.com/v1",
  modelName: "deepseek-chat",
};

const props = defineProps<{
  modelType: ModelType;
  title: string;
  models: ModelRead[];
  providerPresets: ModelProviderPreset[];
  selectedModelId: string;
  saving: boolean;
  testing: boolean;
}>();

const emit = defineEmits<{
  select: [modelId: string];
  save: [data: { modelId?: string; payload: ModelPayload }];
  test: [payload: ModelTestPayload];
  delete: [modelId: string];
}>();

const qaProvider = ref("qwen");
const embeddingProvider = ref("qwen");
const rerankProvider = ref("openai-compatible");
const region = ref<"cn" | "intl">("cn");
const configName = ref("");
const baseUrl = ref("");
const apiKey = ref("");
const modelName = ref("");
const embeddingDimension = ref(1024);
const testResult = ref<Record<string, unknown> | null>(null);
const localError = ref("");
const applyingSelected = ref(false);

const selectedModel = computed(() => props.models.find((model) => model.id === props.selectedModelId));
const currentProvider = computed({
  get() {
    if (props.modelType === "Embedding") return embeddingProvider.value;
    if (props.modelType === "Rerank") return rerankProvider.value;
    return qaProvider.value;
  },
  set(value: string) {
    if (props.modelType === "Embedding") embeddingProvider.value = value;
    else if (props.modelType === "Rerank") rerankProvider.value = value;
    else qaProvider.value = value;
  },
});
const availableProviderPresets = computed(() =>
  props.providerPresets.filter((preset) => preset.model_types.includes(props.modelType)),
);
const selectedProviderPreset = computed(() =>
  availableProviderPresets.value.find((preset) => preset.value === currentProvider.value),
);
const requiresDimension = computed(() => props.modelType === "Embedding");
const apiKeyHint = computed(() => {
  const model = selectedModel.value;
  if (model?.api_key_configured) {
    return `API Key 已配置，尾号 ****${model.api_key_last4 || ""}。留空保存将继续使用旧 Key。`;
  }
  return "首次创建模型必须填写 API Key，后端保存时会加密处理。";
});

function defaultName() {
  if (props.modelType === "Embedding") return "阿里云百炼 Qwen Embedding";
  if (props.modelType === "Rerank") return "Rerank 模型";
  if (currentProvider.value === "deepseek") return "DeepSeek QA";
  return "阿里云百炼 Qwen QA";
}

function applyProviderPreset() {
  if (applyingSelected.value) return;
  localError.value = "";
  const backendPreset = selectedProviderPreset.value;
  if (backendPreset) {
    configName.value = `${backendPreset.label} ${props.modelType === "KnowledgeQA" ? "QA" : props.modelType}`;
    baseUrl.value = backendPreset.default_urls[props.modelType] || baseUrl.value;
    modelName.value = backendPreset.default_models[props.modelType] || modelName.value;
    embeddingDimension.value = backendPreset.embedding_dimensions[props.modelType] || embeddingDimension.value;
    return;
  }
  if (currentProvider.value === "qwen") {
    const preset = qwenPresets[region.value];
    if (props.modelType === "Embedding") {
      configName.value = "阿里云百炼 Qwen Embedding";
      baseUrl.value = preset.baseUrl;
      modelName.value = preset.embeddingModel;
    } else if (props.modelType === "Rerank") {
      configName.value = "阿里云百炼 Qwen Rerank";
      baseUrl.value = preset.rerankBaseUrl;
      modelName.value = preset.rerankModel;
    } else {
      configName.value = "阿里云百炼 Qwen QA";
      baseUrl.value = preset.baseUrl;
      modelName.value = preset.chatModel;
    }
    embeddingDimension.value = preset.embeddingDimension;
  } else if (currentProvider.value === "deepseek") {
    configName.value = "DeepSeek QA";
    baseUrl.value = deepseekPreset.baseUrl;
    modelName.value = deepseekPreset.modelName;
  } else {
    configName.value = defaultName();
  }
}

function applySelectedModel() {
  const model = selectedModel.value;
  applyingSelected.value = true;
  if (model) {
    currentProvider.value = model.provider;
    configName.value = model.name;
    baseUrl.value = model.base_url;
    modelName.value = model.model_name;
    embeddingDimension.value = model.embedding_dimension || embeddingDimension.value;
    apiKey.value = "";
    nextTick(() => {
      applyingSelected.value = false;
    });
  } else {
    applyingSelected.value = false;
    applyProviderPreset();
  }
}

function buildPayload(includeApiKey: boolean): ModelPayload {
  return {
    name: configName.value.trim() || defaultName(),
    type: props.modelType,
    provider: currentProvider.value,
    source: "remote",
    base_url: baseUrl.value.trim(),
    api_key: includeApiKey ? apiKey.value.trim() : undefined,
    model_name: modelName.value.trim(),
    embedding_dimension: requiresDimension.value ? Number(embeddingDimension.value) : undefined,
  };
}

function handleSave() {
  localError.value = "";
  if (!apiKey.value.trim() && !props.selectedModelId) {
    localError.value = "首次创建模型必须填写 API Key。";
    return;
  }
  emit("save", {
    modelId: props.selectedModelId || undefined,
    payload: buildPayload(Boolean(apiKey.value.trim())),
  });
  apiKey.value = "";
}

function handleTest() {
  localError.value = "";
  const modelId = props.selectedModelId || undefined;
  const payload: ModelTestPayload = {
    ...buildPayload(Boolean(apiKey.value.trim())),
    model_id: modelId,
    embedding_dimension: requiresDimension.value ? Number(embeddingDimension.value) : undefined,
  };
  emit("test", payload);
}

watch(() => props.selectedModelId, applySelectedModel, { immediate: true });
watch([currentProvider, region, () => props.providerPresets], applyProviderPreset);
</script>

<template>
  <section class="model-form">
    <header class="section-heading">
      <div>
        <h2>{{ title }}</h2>
        <p>OpenAI-compatible 模型配置，API Key 不会回显到页面。</p>
      </div>
      <a-select
        :model-value="selectedModelId"
        class="model-form__selector"
        placeholder="选择已保存模型"
        allow-clear
        @change="(value) => emit('select', String(value || ''))"
      >
        <a-option v-for="model in models" :key="model.id" :value="model.id">
          {{ model.name }} · {{ model.model_name }}
        </a-option>
      </a-select>
    </header>

    <a-alert v-if="localError" type="error" :content="localError" />

    <div class="model-form__grid">
      <a-form-item label="供应商">
        <a-select v-model="currentProvider" data-testid="qa-provider">
          <a-option v-for="preset in availableProviderPresets" :key="preset.value" :value="preset.value">
            {{ preset.label }}
          </a-option>
        </a-select>
      </a-form-item>
      <a-form-item label="区域">
        <a-select v-model="region" data-testid="embedding-provider" :disabled="currentProvider !== 'qwen'">
          <a-option value="cn">中国内地</a-option>
          <a-option value="intl">国际站</a-option>
        </a-select>
      </a-form-item>
      <a-form-item label="配置名称">
        <a-input v-model="configName" data-testid="model-config-name" />
      </a-form-item>
      <a-form-item label="Base URL">
        <a-input v-model="baseUrl" data-testid="model-base-url" />
      </a-form-item>
      <a-form-item label="API Key">
        <a-input-password v-model="apiKey" data-testid="model-api-key" autocomplete="off" />
        <template #extra>{{ apiKeyHint }}</template>
      </a-form-item>
      <a-form-item label="模型名称">
        <a-input v-model="modelName" data-testid="model-name" />
      </a-form-item>
      <a-form-item v-if="requiresDimension" label="向量维度">
        <a-input-number v-model="embeddingDimension" data-testid="embedding-dimension" :min="1" :max="4096" />
      </a-form-item>
    </div>

    <footer class="model-form__actions">
      <a-button data-testid="test-model" :loading="testing" @click="handleTest">测试模型</a-button>
      <a-button type="primary" data-testid="save-model" :loading="saving" @click="handleSave">保存模型</a-button>
      <a-popconfirm
        v-if="selectedModelId"
        content="确认删除这个模型配置？"
        type="warning"
        @ok="emit('delete', selectedModelId)"
      >
        <a-button status="danger">删除</a-button>
      </a-popconfirm>
    </footer>

    <a-alert
      v-if="testResult"
      type="success"
      :content="JSON.stringify(testResult)"
      data-testid="model-test-result"
    />
  </section>
</template>

<style scoped>
.model-form {
  display: grid;
  gap: 16px;
}

.model-form__selector {
  width: min(360px, 100%);
}

.model-form__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px 18px;
}

.model-form__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10px;
}

@media (max-width: 860px) {
  .model-form__grid {
    grid-template-columns: 1fr;
  }
}
</style>
