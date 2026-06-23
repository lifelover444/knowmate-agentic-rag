import { computed, ref } from "vue";
import { defineStore } from "pinia";
import { getJson, putJson } from "../utils/api";
import type { ParserConfigPayload, ParserConfigRead } from "../types/api";

export const useParserConfigStore = defineStore("parserConfig", () => {
  const mineru = ref<ParserConfigRead | null>(null);
  const loading = ref(false);
  const saving = ref(false);

  const configuredText = computed(() => {
    if (!mineru.value?.api_key_configured) return "未配置";
    return `已配置 ****${mineru.value.api_key_last4 || ""}`;
  });

  async function loadMineruConfig() {
    loading.value = true;
    try {
      mineru.value = await getJson<ParserConfigRead>("/parser-configs/mineru");
      return mineru.value;
    } finally {
      loading.value = false;
    }
  }

  async function saveMineruConfig(payload: ParserConfigPayload) {
    saving.value = true;
    try {
      mineru.value = await putJson<ParserConfigRead, ParserConfigPayload>("/parser-configs/mineru", payload);
      return mineru.value;
    } finally {
      saving.value = false;
    }
  }

  return {
    mineru,
    loading,
    saving,
    configuredText,
    loadMineruConfig,
    saveMineruConfig,
  };
});
