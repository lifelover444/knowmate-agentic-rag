import { computed, ref } from "vue";
import { defineStore } from "pinia";
import { deleteRequest, getJson, patchJson, postJson, postSse } from "../utils/api";
import type {
  AttachmentInput,
  ChatMessageRead,
  ChatSessionBatchDeleteResponse,
  ChatSessionDetail,
  ChatSessionListResponse,
  ChatSessionRead,
  ChatSettings,
  ChatHistoryStats,
  ChatStopResponse,
  KnowledgeSearchResponse,
  MessageSearchResponse,
  MessageSearchResultItem,
  MentionedItem,
  QuickAnswerResponse,
  RecommendedQuestionListResponse,
  RecommendedQuestionRead,
} from "../types/api";

interface AskParams {
  knowledge_base_id: string;
  knowledge_base_ids?: string[];
  knowledge_ids?: string[];
  mentioned_items?: MentionedItem[];
  attachments?: AttachmentInput[];
  top_k: number;
  mode: string;
  enable_rerank: boolean;
  enable_query_rewrite?: boolean;
  temperature?: number | null;
  system_prompt?: string | null;
}

function nowIso(): string {
  return new Date().toISOString();
}

function optimisticMessage(
  role: "user" | "assistant",
  content: string,
  sessionId: string,
  mentionedItems: MentionedItem[] = [],
  attachments: AttachmentInput[] = [],
): ChatMessageRead {
  return {
    id: `local-${role}-${Date.now()}`,
    tenant_id: 10000,
    session_id: sessionId,
    role,
    content,
    mentioned_items: role === "user" ? mentionedItems : [],
    attachments: role === "user" ? attachments : [],
    sources: [],
    status: role === "assistant" ? "streaming" : "completed",
    created_at: nowIso(),
  };
}

export const useChatStore = defineStore("chat", () => {
  const question = ref("知友能做什么？");
  const quickAnswer = ref<QuickAnswerResponse | null>(null);
  const knowledgeSearchQuery = ref("混合检索");
  const knowledgeSearchResult = ref<KnowledgeSearchResponse | null>(null);
  const sessions = ref<ChatSessionRead[]>([]);
  const sessionSearchKeyword = ref("");
  const messageSearchQuery = ref("");
  const messageSearchResults = ref<MessageSearchResultItem[]>([]);
  const chatHistoryStats = ref<ChatHistoryStats | null>(null);
  const selectedSessionIds = ref<string[]>([]);
  const currentSession = ref<ChatSessionDetail | null>(null);
  const messages = ref<ChatMessageRead[]>([]);
  const recommendedQuestions = ref<RecommendedQuestionRead[]>([]);
  const answering = ref(false);
  const loadingSessions = ref(false);
  const searchingMessages = ref(false);
  const deletingSessions = ref(false);
  const searchingKnowledge = ref(false);
  const streamError = ref("");

  const currentAssistant = computed(() => [...messages.value].reverse().find((item) => item.role === "assistant"));
  const filteredSessions = computed(() => sessions.value);

  async function loadSessions(keyword = sessionSearchKeyword.value) {
    loadingSessions.value = true;
    try {
      const query = keyword.trim() ? `?keyword=${encodeURIComponent(keyword.trim())}` : "";
      const response = await getJson<ChatSessionListResponse>(`/chat-sessions${query}`);
      sessions.value = response.items;
      selectedSessionIds.value = selectedSessionIds.value.filter((id) => response.items.some((item) => item.id === id));
      return response.items;
    } finally {
      loadingSessions.value = false;
    }
  }

  async function loadChatHistoryStats() {
    chatHistoryStats.value = await getJson<ChatHistoryStats>("/messages/chat-history-stats");
    return chatHistoryStats.value;
  }

  async function searchMessageHistory() {
    const query = messageSearchQuery.value.trim();
    if (!query) {
      messageSearchResults.value = [];
      return [];
    }
    searchingMessages.value = true;
    try {
      const response = await postJson<MessageSearchResponse>("/messages/search", {
        query,
        mode: "keyword",
        limit: 10,
      });
      messageSearchResults.value = response.items;
      return response.items;
    } finally {
      searchingMessages.value = false;
    }
  }

  async function createSession(knowledgeBaseId: string, title = "新会话", settings?: ChatSettings) {
    const session = await postJson<ChatSessionRead>("/chat-sessions", {
      knowledge_base_id: knowledgeBaseId,
      title,
      settings,
    });
    await loadSession(session.id);
    await loadSessions();
    return session;
  }

  async function loadSession(sessionId: string) {
    currentSession.value = await getJson<ChatSessionDetail>(`/chat-sessions/${sessionId}`);
    messages.value = currentSession.value.messages;
    return currentSession.value;
  }

  async function renameSession(sessionId: string, title: string) {
    const updated = await patchJson<ChatSessionRead>(`/chat-sessions/${sessionId}`, { title });
    await loadSessions();
    if (currentSession.value?.id === sessionId) {
      currentSession.value = { ...currentSession.value, ...updated };
    }
    return updated;
  }

  async function togglePin(session: ChatSessionRead) {
    const updated = await patchJson<ChatSessionRead>(`/chat-sessions/${session.id}`, {
      is_pinned: !session.is_pinned,
    });
    await loadSessions();
    return updated;
  }

  async function deleteSession(sessionId: string) {
    await deleteRequest(`/chat-sessions/${sessionId}`);
    if (currentSession.value?.id === sessionId) {
      currentSession.value = null;
      messages.value = [];
    }
    await loadSessions();
  }

  async function batchDeleteSessions() {
    deletingSessions.value = true;
    try {
      const response = await postJson<ChatSessionBatchDeleteResponse>("/chat-sessions/batch-delete", {
        session_ids: selectedSessionIds.value,
      });
      if (currentSession.value && selectedSessionIds.value.includes(currentSession.value.id)) {
        currentSession.value = null;
        messages.value = [];
      }
      selectedSessionIds.value = [];
      await loadSessions();
      return response;
    } finally {
      deletingSessions.value = false;
    }
  }

  async function loadRecommendedQuestions(knowledgeBaseId: string) {
    if (!knowledgeBaseId) {
      recommendedQuestions.value = [];
      return [];
    }
    const response = await getJson<RecommendedQuestionListResponse>(
      `/chat-sessions/recommended-questions?knowledge_base_id=${encodeURIComponent(knowledgeBaseId)}&limit=6`,
    );
    recommendedQuestions.value = response.items;
    return response.items;
  }

  function useRecommendedQuestion(questionText: string) {
    question.value = questionText;
  }

  async function askQuestion(params: AskParams) {
    answering.value = true;
    streamError.value = "";
    quickAnswer.value = null;
    const sessionIdBeforeSend = currentSession.value?.id || "";
    if (sessionIdBeforeSend) {
      messages.value.push(
        optimisticMessage(
          "user",
          question.value,
          sessionIdBeforeSend,
          params.mentioned_items || [],
          params.attachments || [],
        ),
      );
      messages.value.push(optimisticMessage("assistant", "", sessionIdBeforeSend));
    }
    try {
      await postSse("/quick-answer/stream", {
        session_id: currentSession.value?.id,
        knowledge_base_id: params.knowledge_base_id,
        knowledge_base_ids: params.knowledge_base_ids,
        knowledge_ids: params.knowledge_ids,
        mentioned_items: params.mentioned_items,
        attachments: params.attachments,
        query: question.value,
        top_k: params.top_k,
        mode: params.mode,
        enable_rerank: params.enable_rerank,
        enable_query_rewrite: params.enable_query_rewrite,
        temperature: params.temperature,
        system_prompt: params.system_prompt,
      }, (sse) => {
        if (sse.event === "session") {
          currentSession.value = { ...(sse.data as unknown as ChatSessionDetail), messages: messages.value };
          if (!sessionIdBeforeSend) {
            messages.value.push(
              optimisticMessage(
                "user",
                question.value,
                currentSession.value.id,
                params.mentioned_items || [],
                params.attachments || [],
              ),
            );
            messages.value.push(optimisticMessage("assistant", "", currentSession.value.id));
          }
        }
        if (sse.event === "token") {
          const token = String(sse.data.text || "");
          const assistant = currentAssistant.value;
          if (assistant) assistant.content += token;
        }
        if (sse.event === "final") {
          const finalMessage = sse.data.assistant_message as unknown as ChatMessageRead;
          const index = messages.value.findIndex((item) => item.role === "assistant" && item.status === "streaming");
          if (index >= 0) messages.value.splice(index, 1, finalMessage);
          quickAnswer.value = {
            answer: String(sse.data.answer || ""),
            sources: finalMessage.sources || [],
            retrieval_trace: finalMessage.retrieval_trace || null,
          };
        }
        if (sse.event === "stopped") {
          const stoppedMessage = sse.data.assistant_message as unknown as ChatMessageRead;
          const index = messages.value.findIndex((item) => item.role === "assistant" && item.status === "streaming");
          if (index >= 0) messages.value.splice(index, 1, stoppedMessage);
          streamError.value = String(sse.data.error_message || "用户已停止生成");
        }
        if (sse.event === "error") {
          streamError.value = String(sse.data.error || sse.data.message || "回答失败");
        }
      });
      question.value = "";
      recommendedQuestions.value = [];
      await loadSessions();
      if (currentSession.value?.id) await loadSession(currentSession.value.id);
      return quickAnswer.value;
    } finally {
      answering.value = false;
    }
  }

  async function stopGeneration(sessionId = currentSession.value?.id || "") {
    if (!sessionId) return null;
    const response = await postJson<ChatStopResponse>(`/chat-sessions/${sessionId}/stop`, {});
    streamError.value = response.message || "用户已停止生成";
    return response;
  }

  async function searchKnowledge(params: AskParams) {
    searchingKnowledge.value = true;
    try {
      knowledgeSearchResult.value = await postJson<KnowledgeSearchResponse>("/knowledge-search", {
        knowledge_base_id: params.knowledge_base_id,
        knowledge_base_ids: params.knowledge_base_ids,
        knowledge_ids: params.knowledge_ids,
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
    sessions,
    sessionSearchKeyword,
    messageSearchQuery,
    messageSearchResults,
    chatHistoryStats,
    selectedSessionIds,
    filteredSessions,
    currentSession,
    messages,
    recommendedQuestions,
    answering,
    loadingSessions,
    searchingMessages,
    deletingSessions,
    searchingKnowledge,
    streamError,
    loadSessions,
    loadChatHistoryStats,
    searchMessageHistory,
    createSession,
    loadSession,
    renameSession,
    togglePin,
    deleteSession,
    batchDeleteSessions,
    loadRecommendedQuestions,
    useRecommendedQuestion,
    askQuestion,
    stopGeneration,
    searchKnowledge,
  };
});
