import { ref } from "vue";
import { defineStore } from "pinia";
import { deleteRequest, getJson, postJson, putJson } from "../utils/api";
import type { VectorStorePayload, VectorStoreRead, VectorStoreTypeRead } from "../types/api";

export const useVectorStoresStore = defineStore("vectorStores", () => {
  const vectorStores = ref<VectorStoreRead[]>([]);
  const vectorStoreTypes = ref<VectorStoreTypeRead[]>([]);
  const loading = ref(false);
  const testing = ref(false);

  async function loadVectorStores() {
    loading.value = true;
    try {
      vectorStores.value = await getJson<VectorStoreRead[]>("/vector-stores");
      return vectorStores.value;
    } finally {
      loading.value = false;
    }
  }

  async function loadVectorStoreTypes() {
    vectorStoreTypes.value = await getJson<VectorStoreTypeRead[]>("/vector-stores/types");
    return vectorStoreTypes.value;
  }

  async function createVectorStore(payload: VectorStorePayload) {
    const created = await postJson<VectorStoreRead, VectorStorePayload>("/vector-stores", payload);
    await loadVectorStores();
    return created;
  }

  async function updateVectorStore(id: string, payload: Partial<VectorStorePayload>) {
    const updated = await putJson<VectorStoreRead>(`/vector-stores/${id}`, payload);
    await loadVectorStores();
    return updated;
  }

  async function deleteVectorStore(id: string) {
    await deleteRequest(`/vector-stores/${id}`);
    await loadVectorStores();
  }

  async function testVectorStore(payload: { provider: string; config_json: Record<string, unknown> }) {
    testing.value = true;
    try {
      return await postJson<{ ok: boolean; message: string }>("/vector-stores/test", payload);
    } finally {
      testing.value = false;
    }
  }

  return {
    vectorStores,
    vectorStoreTypes,
    loading,
    testing,
    loadVectorStores,
    loadVectorStoreTypes,
    createVectorStore,
    updateVectorStore,
    deleteVectorStore,
    testVectorStore,
  };
});
