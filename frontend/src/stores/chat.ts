import { ref } from "vue";
import { defineStore } from "pinia";
import { postJson } from "../utils/api";
import type { KnowledgeSearchResponse, QuickAnswerResponse } from "../types/api";

interface AskParams {
  knowledge_base_id: string;
  top_k: number;
  mode: string;
  enable_rerank: boolean;
}

export const useChatStore = defineStore("chat", () => {
  const question = ref("知友能做什么？");
  const quickAnswer = ref<QuickAnswerResponse | null>(null);
  const knowledgeSearchQuery = ref("混合检索");
  const knowledgeSearchResult = ref<KnowledgeSearchResponse | null>(null);
  const answering = ref(false);
  const searchingKnowledge = ref(false);

  async function askQuestion(params: AskParams) {
    answering.value = true;
    try {
      quickAnswer.value = await postJson<QuickAnswerResponse>("/quick-answer", {
        knowledge_base_id: params.knowledge_base_id,
        query: question.value,
        top_k: params.top_k,
        mode: params.mode,
        enable_rerank: params.enable_rerank,
      });
      return quickAnswer.value;
    } finally {
      answering.value = false;
    }
  }

  async function searchKnowledge(params: AskParams) {
    searchingKnowledge.value = true;
    try {
      knowledgeSearchResult.value = await postJson<KnowledgeSearchResponse>("/knowledge-search", {
        knowledge_base_id: params.knowledge_base_id,
        query: knowledgeSearchQuery.value,
        top_k: params.top_k,
        mode: params.mode,
        enable_rerank: params.enable_rerank,
      });
      return knowledgeSearchResult.value;
    } finally {
      searchingKnowledge.value = false;
    }
  }

  return {
    question,
    quickAnswer,
    knowledgeSearchQuery,
    knowledgeSearchResult,
    answering,
    searchingKnowledge,
    askQuestion,
    searchKnowledge,
  };
});
