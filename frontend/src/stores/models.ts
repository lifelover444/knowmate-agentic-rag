import { computed, ref } from "vue";
import { defineStore } from "pinia";
import { deleteRequest, getJson, postJson, putJson } from "../utils/api";
import type { ModelPayload, ModelProviderPreset, ModelRead, ModelTestPayload } from "../types/api";

interface LegacyModelConfig {
  provider: string;
  name: string;
  base_url: string;
  chat_model: string;
  embedding_model: string;
  embedding_dimension: number;
  api_key_configured: boolean;
  api_key_last4?: string | null;
}

export const useModelsStore = defineStore("models", () => {
  const models = ref<ModelRead[]>([]);
  const providerPresets = ref<ModelProviderPreset[]>([]);
  const selectedChatModelId = ref("");
  const selectedEmbeddingModelId = ref("");
  const selectedRerankModelId = ref("");
  const loading = ref(false);
  const saving = ref(false);
  const testing = ref(false);
  const deleting = ref(false);
  const legacyConfig = ref<LegacyModelConfig | null>(null);

  function isRealSelectableModel(model: ModelRead): boolean {
    const modelName = model.model_name.trim().toLowerCase();
    return model.model_name !== "fake-embedding" && !modelName.startsWith("fake-");
  }

  const chatModels = computed(() =>
    models.value.filter((model) => model.type === "KnowledgeQA" && isRealSelectableModel(model)),
  );
  const embeddingModels = computed(() =>
    models.value.filter((model) => model.type === "Embedding" && isRealSelectableModel(model)),
  );
  const rerankModels = computed(() => models.value.filter((model) => model.type === "Rerank"));
  const modelGroups = computed(() => [
    { type: "KnowledgeQA", label: "KnowledgeQA 模型组", models: chatModels.value },
    { type: "Embedding", label: "Embedding 模型组", models: embeddingModels.value },
    { type: "Rerank", label: "Rerank 模型组", models: rerankModels.value },
  ]);

  function selectAvailableModels() {
    if (!chatModels.value.some((model) => model.id === selectedChatModelId.value)) {
      selectedChatModelId.value = chatModels.value[0]?.id || "";
    }
    if (!embeddingModels.value.some((model) => model.id === selectedEmbeddingModelId.value)) {
      selectedEmbeddingModelId.value = embeddingModels.value[0]?.id || "";
    }
    if (!rerankModels.value.some((model) => model.id === selectedRerankModelId.value)) {
      selectedRerankModelId.value = rerankModels.value[0]?.id || "";
    }
  }

  async function loadLegacyModelConfig() {
    legacyConfig.value = await getJson<LegacyModelConfig>("/model-config");
  }

  async function loadProviderPresets() {
    providerPresets.value = await getJson<ModelProviderPreset[]>("/models/providers");
    return providerPresets.value;
  }

  async function loadModels() {
    loading.value = true;
    try {
      const [modelList] = await Promise.all([
        getJson<ModelRead[]>("/models"),
        loadProviderPresets().catch(() => []),
        loadLegacyModelConfig().catch(() => null),
      ]);
      models.value = modelList;
      selectAvailableModels();
    } finally {
      loading.value = false;
    }
  }

  async function saveModel(payload: ModelPayload, modelId?: string) {
    saving.value = true;
    try {
      const sanitizedPayload = { ...payload };
      delete sanitizedPayload.api_key;
      const saved = modelId
        ? await putJson<ModelRead, Partial<ModelPayload>>(`/models/${modelId}`, sanitizedPayload)
        : await postJson<ModelRead, ModelPayload>("/models", payload);
      if (payload.api_key?.trim()) {
        await updateCredential(saved.id, payload.api_key.trim());
      }
      await loadModels();
      if (saved.type === "KnowledgeQA") selectedChatModelId.value = saved.id;
      if (saved.type === "Embedding") selectedEmbeddingModelId.value = saved.id;
      if (saved.type === "Rerank") selectedRerankModelId.value = saved.id;
      return saved;
    } finally {
      saving.value = false;
    }
  }

  async function deleteModel(modelId: string) {
    deleting.value = true;
    try {
      await deleteRequest(`/models/${modelId}`);
      await loadModels();
    } finally {
      deleting.value = false;
    }
  }

  async function testModel(payload: ModelTestPayload) {
    testing.value = true;
    try {
      return await postJson<Record<string, unknown>, ModelTestPayload>("/models/test", payload);
    } finally {
      testing.value = false;
    }
  }

  async function updateCredential(modelId: string, apiKey: string) {
    await putJson(`/models/${modelId}/credentials`, { api_key: apiKey });
  }

  return {
    models,
    providerPresets,
    selectedChatModelId,
    selectedEmbeddingModelId,
    selectedRerankModelId,
    loading,
    saving,
    testing,
    deleting,
    legacyConfig,
    chatModels,
    embeddingModels,
    rerankModels,
    modelGroups,
    loadProviderPresets,
    loadModels,
    saveModel,
    deleteModel,
    testModel,
    updateCredential,
  };
});
