import { ref } from "vue";
import { defineStore } from "pinia";
import { getJson, postJson } from "../utils/api";
import type { EvaluationCreatePayload, EvaluationRunDetail, EvaluationRunRead, EvaluationTestsetRead } from "../types/api";

export const evaluationMaxPolls = 240;

export const useEvaluationStore = defineStore("evaluations", () => {
  const runs = ref<EvaluationRunRead[]>([]);
  const currentRun = ref<EvaluationRunDetail | null>(null);
  const testsets = ref<EvaluationTestsetRead[]>([]);
  const loading = ref(false);
  const loadingTestsets = ref(false);
  const creating = ref(false);
  const polling = ref(false);

  async function loadEvaluations(knowledgeBaseId = "") {
    loading.value = true;
    try {
      const params = new URLSearchParams();
      if (knowledgeBaseId) params.set("knowledge_base_id", knowledgeBaseId);
      const suffix = params.toString() ? `?${params.toString()}` : "";
      runs.value = await getJson<EvaluationRunRead[]>(`/evaluations${suffix}`);
      return runs.value;
    } finally {
      loading.value = false;
    }
  }

  async function loadEvaluation(runId: string) {
    currentRun.value = await getJson<EvaluationRunDetail>(`/evaluations/${runId}`);
    return currentRun.value;
  }

  async function loadTestsets(knowledgeBaseId = "") {
    loadingTestsets.value = true;
    try {
      const params = new URLSearchParams();
      if (knowledgeBaseId) params.set("knowledge_base_id", knowledgeBaseId);
      const suffix = params.toString() ? `?${params.toString()}` : "";
      testsets.value = await getJson<EvaluationTestsetRead[]>(`/evaluations/testsets${suffix}`);
      return testsets.value;
    } finally {
      loadingTestsets.value = false;
    }
  }

  async function createEvaluation(payload: EvaluationCreatePayload) {
    creating.value = true;
    try {
      const run = await postJson<EvaluationRunRead, EvaluationCreatePayload>("/evaluations", payload);
      await loadEvaluations(payload.knowledge_base_id);
      return run;
    } finally {
      creating.value = false;
    }
  }

  async function markBaseline(runId: string) {
    const run = await postJson<EvaluationRunRead, Record<string, never>>(`/evaluations/${runId}/baseline`, {});
    if (currentRun.value?.id === runId) await loadEvaluation(runId);
    await loadEvaluations(run.knowledge_base_id);
    return run;
  }

  async function pollEvaluation(runId: string) {
    polling.value = true;
    try {
      for (let index = 0; index < evaluationMaxPolls; index += 1) {
        const run = await loadEvaluation(runId);
        if (run.status === "completed" || run.status === "failed") return run;
        await new Promise((resolve) => setTimeout(resolve, 1200));
      }
      throw new Error("评测仍在后台执行，请稍后刷新查看量化结果。");
    } finally {
      polling.value = false;
    }
  }

  return {
    runs,
    currentRun,
    testsets,
    loading,
    loadingTestsets,
    creating,
    polling,
    loadEvaluations,
    loadEvaluation,
    loadTestsets,
    createEvaluation,
    markBaseline,
    pollEvaluation,
  };
});
