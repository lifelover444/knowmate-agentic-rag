<script setup lang="ts">
import MarkdownIt from "markdown-it";
import hljs from "highlight.js";
import { Message } from "@arco-design/web-vue";
import { computed, nextTick, onMounted, ref, watch } from "vue";
import SourceCard from "../components/SourceCard.vue";
import { useChatStore } from "../stores/chat";
import { useKnowledgeBaseStore } from "../stores/knowledgeBase";
import { useRetrievalStore } from "../stores/retrieval";
import type { AttachmentInput, ChatMessageRead, ChatSessionRead, MentionedItem, RetrievalTraceStage } from "../types/api";
import { formatApiError } from "../utils/api";

const chat = useChatStore();
const kbStore = useKnowledgeBaseStore();
const retrieval = useRetrievalStore();
const selectedKbId = ref("");
const selectedMentionKbIds = ref<string[]>([]);
const selectedMentionDocumentIds = ref<string[]>([]);
const enableQueryRewrite = ref(false);
const renameVisible = ref(false);
const renameTitle = ref("");
const renamingSessionId = ref("");
const attachmentInput = ref<HTMLInputElement | null>(null);
const messageListRef = ref<HTMLElement | null>(null);
const shouldStickToBottom = ref(true);
const chatAttachments = ref<AttachmentInput[]>([]);

const acceptedAttachmentTypes = ".txt,.md,.markdown,.csv,.json";
const maxAttachmentBytes = 64 * 1024;
const maxAttachmentLines = 200;
const maxAttachmentChars = 12000;

const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
  highlight(code, language) {
    if (language && hljs.getLanguage(language)) {
      return hljs.highlight(code, { language }).value;
    }
    return hljs.highlightAuto(code).value;
  },
});

const selectedKb = computed(() => kbStore.knowledgeBases.find((item) => item.id === selectedKbId.value));
const mentionedItems = computed<MentionedItem[]>(() => [
  ...selectedMentionKbIds.value
    .map((id) => kbStore.knowledgeBases.find((kb) => kb.id === id))
    .filter(Boolean)
    .map((kb) => ({
      id: kb!.id,
      name: kb!.name,
      type: "kb",
      kb_type: kb!.kb_type,
    })),
  ...selectedMentionDocumentIds.value
    .map((id) => kbStore.documents.find((document) => document.id === id))
    .filter(Boolean)
    .map((document) => ({
      id: document!.id,
      name: document!.title,
      type: "file",
    })),
]);
const effectiveKnowledgeBaseIds = computed(() => {
  // 没有选择 scope 时保留当前单 KB 默认行为。
  return selectedMentionKbIds.value.length ? selectedMentionKbIds.value : selectedKbId.value ? [selectedKbId.value] : [];
});
const selectedKbAllowsRerank = computed(() => {
  const strategy = selectedKb.value?.indexing_strategy as Record<string, unknown> | undefined;
  return Boolean(strategy?.enable_rerank);
});
const rerankBlockedByKb = computed(() => retrieval.retrievalEnableRerank && selectedKbId.value && !selectedKbAllowsRerank.value);
const lastRequestState = computed(() => chat.currentSession?.last_request_state || {});
const lastRequestStatusText = computed(() => {
  const status = String(lastRequestState.value.status || "");
  if (status === "completed") return "已完成";
  if (status === "running") return "生成中";
  if (status === "cancelled") return "已停止";
  if (status === "failed") return "失败";
  return "暂无";
});
const currentChatTitle = computed(() => {
  const title = chat.currentSession?.title || selectedKb.value?.name || "新对话";
  return title.replace(/^我\s+/, "");
});

function isMessageListNearBottom(): boolean {
  const el = messageListRef.value;
  if (!el) return true;
  return el.scrollHeight - el.scrollTop - el.clientHeight < 96;
}

function scrollMessagesToBottom(behavior: ScrollBehavior = "auto") {
  const el = messageListRef.value;
  if (!el) return;
  el.scrollTo({ top: el.scrollHeight, behavior });
}

function scheduleScrollToBottom(behavior: ScrollBehavior = "auto") {
  nextTick(() => {
    requestAnimationFrame(() => scrollMessagesToBottom(behavior));
  });
}

function handleMessageListScroll() {
  shouldStickToBottom.value = isMessageListNearBottom();
}

function forceMessageListStickToBottom(behavior: ScrollBehavior = "auto") {
  shouldStickToBottom.value = true;
  scheduleScrollToBottom(behavior);
}

function renderMarkdown(content: string): string {
  return md.render(content || "");
}

function displayUserContent(content: string): string {
  return (content || "").replace(/^我\s*\n/, "");
}

function shortTime(value: string): string {
  return new Date(value).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function lastRequestList(value: unknown): string {
  return Array.isArray(value) && value.length ? value.join(", ") : "-";
}

function lastRequestDuration(value: unknown): string {
  const duration = Number(value || 0);
  return duration ? `${duration} ms` : "-";
}

function requestParams() {
  return {
    knowledge_base_id: selectedKbId.value,
    knowledge_base_ids: effectiveKnowledgeBaseIds.value,
    knowledge_ids: selectedMentionDocumentIds.value,
    mentioned_items: mentionedItems.value,
    top_k: Number(retrieval.retrievalRerankTopK || 10),
    mode: retrieval.retrievalMode,
    enable_rerank: retrieval.retrievalEnableRerank,
    enable_query_rewrite: enableQueryRewrite.value,
    attachments: chatAttachments.value,
  };
}

function clearMentionScope() {
  selectedMentionKbIds.value = [];
  selectedMentionDocumentIds.value = [];
}

function attachmentFileType(filename: string): string {
  return filename.split(".").pop()?.toLowerCase() || "";
}

function isSupportedAttachment(filename: string): boolean {
  return ["txt", "md", "markdown", "csv", "json"].includes(attachmentFileType(filename));
}

function attachmentWillTruncate(content: string): boolean {
  return content.split(/\r\n|\r|\n/).length > maxAttachmentLines || content.length > maxAttachmentChars;
}

function removeAttachment(filename: string) {
  chatAttachments.value = chatAttachments.value.filter((item) => item.filename !== filename);
}

async function handleAttachmentChange(event: Event) {
  const input = event.target as HTMLInputElement;
  const files = Array.from(input.files || []);
  input.value = "";
  for (const file of files) {
    if (!isSupportedAttachment(file.name)) {
      Message.error(`不支持的附件类型：${file.name}，当前仅支持 txt/md/csv/json`);
      continue;
    }
    if (file.size > maxAttachmentBytes) {
      Message.error(`附件 ${file.name} 超过大小限制，当前仅支持 64KB 以内的文本附件`);
      continue;
    }
    const content = await file.text();
    const attachment: AttachmentInput = {
      filename: file.name,
      mime_type: file.type || null,
      size: file.size,
      content,
      truncated: attachmentWillTruncate(content),
    };
    chatAttachments.value = [
      ...chatAttachments.value.filter((item) => item.filename !== file.name),
      attachment,
    ].slice(0, 5);
  }
}

async function newSession() {
  if (!selectedKbId.value) {
    Message.error("请先选择知识库");
    return;
  }
  try {
    await chat.createSession(selectedKbId.value, `${selectedKb.value?.name || "知识库"}会话`, {
      mode: retrieval.retrievalMode,
      top_k: Number(retrieval.retrievalRerankTopK || 10),
      enable_rerank: retrieval.retrievalEnableRerank,
      enable_query_rewrite: enableQueryRewrite.value,
    });
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

async function selectSession(session: ChatSessionRead) {
  try {
    await chat.loadSession(session.id);
    selectedKbId.value = session.knowledge_base_id;
    enableQueryRewrite.value = Boolean((session.settings as Record<string, unknown>)?.enable_query_rewrite);
    forceMessageListStickToBottom();
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

async function openHistoryResult(sessionId: string) {
  try {
    const session = await chat.loadSession(sessionId);
    selectedKbId.value = session.knowledge_base_id;
    enableQueryRewrite.value = Boolean((session.settings as Record<string, unknown>)?.enable_query_rewrite);
    forceMessageListStickToBottom();
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

function openRename(session: ChatSessionRead) {
  renamingSessionId.value = session.id;
  renameTitle.value = session.title;
  renameVisible.value = true;
}

async function submitRename() {
  try {
    await chat.renameSession(renamingSessionId.value, renameTitle.value);
    renameVisible.value = false;
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

async function deleteSession(session: ChatSessionRead) {
  try {
    await chat.deleteSession(session.id);
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

async function searchSessions() {
  try {
    await chat.loadSessions(chat.sessionSearchKeyword);
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

async function searchMessageHistory() {
  try {
    await chat.searchMessageHistory();
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

function toggleSessionSelection(sessionId: string, checked: boolean) {
  if (checked && !chat.selectedSessionIds.includes(sessionId)) {
    chat.selectedSessionIds.push(sessionId);
  }
  if (!checked) {
    chat.selectedSessionIds = chat.selectedSessionIds.filter((id) => id !== sessionId);
  }
}

async function batchDeleteSessions() {
  try {
    const result = await chat.batchDeleteSessions();
    if (result?.failed) {
      Message.warning(`已删除 ${result.deleted} 个会话，${result.failed} 个失败。`);
    } else {
      Message.success(`已删除 ${result?.deleted || 0} 个会话。`);
    }
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

async function togglePin(session: ChatSessionRead) {
  try {
    await chat.togglePin(session);
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

function useRecommendedQuestion(questionText: string) {
  chat.useRecommendedQuestion(questionText);
}

async function askQuestion() {
  if (rerankBlockedByKb.value) {
    Message.error("当前知识库未启用重排，请先到知识库列表编辑配置打开 rerank。");
    return;
  }
  forceMessageListStickToBottom();
  try {
    await chat.askQuestion(requestParams());
    chatAttachments.value = [];
    if (chat.streamError) Message.error(chat.streamError);
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

async function stopGeneration() {
  try {
    const response = await chat.stopGeneration();
    Message.info(response?.message || "用户已停止生成");
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

async function searchKnowledge() {
  if (rerankBlockedByKb.value) {
    Message.error("当前知识库未启用重排，请先到知识库列表编辑配置打开 rerank。");
    return;
  }
  try {
    await chat.searchKnowledge(requestParams());
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

function messageTrace(message: ChatMessageRead): Record<string, unknown> {
  return message.retrieval_trace || {};
}

function traceStages(message: ChatMessageRead): RetrievalTraceStage[] {
  const stages = messageTrace(message).stages;
  return Array.isArray(stages) ? stages as RetrievalTraceStage[] : [];
}

function promptContextSummary(message: ChatMessageRead): string {
  const trace = messageTrace(message);
  return String(message.prompt_context_summary || trace.prompt_context_summary || "");
}

function traceHitSummary(message: ChatMessageRead): string {
  const trace = messageTrace(message);
  const parts = [
    `vector_hits: ${traceValueText(trace.vector_hits)}`,
    `keyword_hits: ${traceValueText(trace.keyword_hits)}`,
    `rrf_hits: ${traceValueText(trace.rrf_hits)}`,
    `rerank_hits: ${traceValueText(trace.rerank_hits)}`,
  ];
  return parts.join(" · ");
}

function selectedContexts(message: ChatMessageRead): Record<string, unknown>[] {
  const contexts = messageTrace(message).selected_contexts;
  return Array.isArray(contexts) ? contexts as Record<string, unknown>[] : [];
}

function selectedContextTitle(context: Record<string, unknown>): string {
  return String(context.document_title || context.document_id || "未知来源");
}

function knowledgeSearchTraceStages(): RetrievalTraceStage[] {
  return chat.knowledgeSearchResult?.diagnostics?.stages || [];
}

function traceStageLabel(name: unknown): string {
  const labels: Record<string, string> = {
    rewrite: "问题改写",
    vector: "向量检索",
    keyword: "关键词检索",
    rrf: "RRF 合并",
    parent_expand: "父子块扩展",
    deduplicate: "去重",
    faq_merge: "FAQ 合并",
    rerank: "重排",
    context_select: "上下文选择",
    answer: "回答生成",
  };
  const key = String(name || "");
  return labels[key] || key || "未知阶段";
}

function traceStatusText(status: unknown): string {
  const labels: Record<string, string> = {
    done: "已完成",
    skipped: "已跳过",
    failed: "失败",
    pending: "待生成",
    cancelled: "已停止",
  };
  const key = String(status || "");
  return labels[key] || key || "未知";
}

function traceStatusColor(status: unknown): string {
  const key = String(status || "");
  if (key === "done") return "green";
  if (key === "failed") return "red";
  if (key === "cancelled") return "orange";
  if (key === "pending") return "blue";
  return "gray";
}

function traceReasonText(value: unknown): string {
  const labels: Record<string, string> = {
    mode_not_applicable: "不适用于当前检索模式",
    no_hits: "没有命中来源",
  };
  const key = String(value || "");
  return labels[key] || key;
}

function traceValueText(value: unknown): string {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "boolean") return value ? "是" : "否";
  if (typeof value === "number" || typeof value === "string") return traceReasonText(value);
  if (Array.isArray(value)) return value.length ? value.map(traceValueText).join(", ") : "-";
  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>)
      .filter(([_key, entryValue]) => entryValue !== null && entryValue !== undefined && entryValue !== "")
      .slice(0, 4)
      .map(([key, entryValue]) => `${key}: ${traceValueText(entryValue)}`);
    return entries.length ? entries.join("；") : "-";
  }
  return String(value);
}

function traceStageSummary(stage: RetrievalTraceStage): string {
  const output = stage.output || {};
  const input = stage.input || {};
  const parts: string[] = [];
  const fields: [string, string, Record<string, unknown>][] = [
    ["命中", "hit_count", output],
    ["输入", "input_count", output],
    ["输出", "output_count", output],
    ["候选", "candidate_count", input],
    ["扩展", "expanded_count", output],
    ["过滤", "removed_count", output],
    ["Boost", "boost_count", output],
    ["rerank 输入", "rerank_input_count", output],
    ["rerank 输出", "rerank_output_count", output],
    ["选中上下文", "selected_context_count", output],
    ["原因", "reason", output],
    ["阈值", "threshold", input],
  ];
  for (const [label, key, source] of fields) {
    if (source[key] !== undefined && source[key] !== null && source[key] !== "") {
      parts.push(`${label}: ${traceValueText(source[key])}`);
    }
  }
  if (stage.error_message) parts.push(`错误: ${stage.error_message}`);
  return parts.length ? parts.join(" · ") : "暂无摘要";
}

onMounted(() => {
  Promise.all([
    kbStore.loadKnowledgeBases(),
    retrieval.loadRetrievalConfig(),
    chat.loadSessions(),
    chat.loadChatHistoryStats(),
  ]).then(() => {
    selectedKbId.value = chat.currentSession?.knowledge_base_id || kbStore.knowledgeBases[0]?.id || "";
    if (!chat.currentSession && chat.sessions[0]) {
      selectSession(chat.sessions[0]);
    } else if (selectedKbId.value) {
      chat.loadRecommendedQuestions(selectedKbId.value);
    }
    forceMessageListStickToBottom();
  }).catch((error) => {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  });
});

watch(selectedKbId, (kbId) => {
  selectedMentionDocumentIds.value = [];
  if (kbId) {
    kbStore.loadDocuments(kbId).catch((error) => {
      Message.error(`选择范围加载失败：${formatApiError(error instanceof Error ? error.message : error)}`);
    });
  }
  if (!chat.currentSession || !chat.messages.length) {
    chat.loadRecommendedQuestions(kbId).catch((error) => {
      Message.error(formatApiError(error instanceof Error ? error.message : error));
    });
  }
});

watch(() => chat.currentSession?.knowledge_base_id, (kbId) => {
  if (kbId && kbId !== selectedKbId.value) {
    selectedKbId.value = kbId;
  }
});

watch(
  () => chat.messages.map((message) => `${message.id}:${message.status || ""}:${message.content.length}`).join("|"),
  () => {
    if (shouldStickToBottom.value) scheduleScrollToBottom();
  },
  { flush: "post" },
);
</script>

<template>
  <main class="page-shell chat-page">
    <section class="chat-workbench">
      <aside class="chat-sidebar">
        <div class="chat-sidebar__top">
          <a-button type="primary" data-testid="new-chat-session" :disabled="!selectedKbId" @click="newSession">新建会话</a-button>
          <a-input-search
            v-model="chat.sessionSearchKeyword"
            data-testid="chat-session-search"
            placeholder="搜索会话"
            allow-clear
            @search="searchSessions"
            @press-enter="searchSessions"
          />
          <div class="session-batch-actions">
            <span>{{ chat.selectedSessionIds.length }} 已选</span>
            <a-popconfirm content="确认批量删除所选会话？" @ok="batchDeleteSessions">
              <a-button
                size="small"
                status="danger"
                :loading="chat.deletingSessions"
                :disabled="!chat.selectedSessionIds.length"
              >
                批量删除
              </a-button>
            </a-popconfirm>
          </div>
        </div>
        <section class="history-search-panel" data-testid="message-history-search">
          <header>
            <strong>历史问答搜索</strong>
            <span>
              可检索消息 {{ chat.chatHistoryStats?.message_count || 0 }}
            </span>
          </header>
          <a-input-search
            v-model="chat.messageSearchQuery"
            data-testid="message-history-search-input"
            placeholder="搜索历史回答"
            allow-clear
            :loading="chat.searchingMessages"
            @search="searchMessageHistory"
            @press-enter="searchMessageHistory"
          />
          <div v-if="chat.messageSearchResults.length" class="history-search-results">
            <button
              v-for="item in chat.messageSearchResults"
              :key="`${item.session_id}-${item.created_at}`"
              type="button"
              @click="openHistoryResult(item.session_id)"
            >
              <strong>{{ item.session_title }}</strong>
              <span>{{ item.query_content }}</span>
              <small>{{ item.answer_snippet }}</small>
            </button>
          </div>
          <a-empty
            v-else-if="chat.messageSearchQuery.trim() && !chat.searchingMessages"
            description="暂无历史问答命中"
          />
        </section>
        <div class="session-list" data-testid="chat-session-list">
          <div
            v-for="session in chat.filteredSessions"
            :key="session.id"
            class="session-item"
            :class="{ 'session-item--active': chat.currentSession?.id === session.id }"
          >
            <input
              type="checkbox"
              :checked="chat.selectedSessionIds.includes(session.id)"
              @change="toggleSessionSelection(session.id, ($event.target as HTMLInputElement).checked)"
            />
            <button type="button" @click="selectSession(session)">
              <span>{{ session.is_pinned ? "置顶 · " : "" }}{{ session.title }}</span>
              <small>{{ shortTime(session.last_message_at) }}</small>
            </button>
          </div>
          <a-empty v-if="!chat.filteredSessions.length" description="暂无会话" />
        </div>
      </aside>

      <section class="chat-main">
        <header class="chat-session-header">
          <h1>{{ currentChatTitle }}</h1>
        </header>
        <div class="chat-toolbar">
          <div class="chat-toolbar__primary">
            <a-form-item label="知识库" class="kb-select-item chat-toolbar__kb">
              <a-select v-model="selectedKbId" placeholder="请选择知识库" data-testid="knowledge-base-select">
                <a-option v-for="kb in kbStore.knowledgeBases" :key="kb.id" :value="kb.id">
                  {{ kb.name }} · {{ kb.document_count }} 文档 · {{ kb.chunk_count }} chunks
                </a-option>
              </a-select>
            </a-form-item>
            <div class="chat-toolbar__meta">
              <strong>{{ chat.currentSession?.title || "未选择会话" }}</strong>
              <span>{{ selectedKb ? `${selectedKb.document_count} 文档 · ${selectedKb.chunk_count} chunks` : "请选择知识库" }}</span>
            </div>
          </div>
          <div class="chat-toolbar__actions">
            <a-switch v-model="enableQueryRewrite" data-testid="enable-query-rewrite" />
            <span class="setting-label">Query rewrite</span>
            <a-button v-if="chat.currentSession" size="small" @click="openRename(chat.currentSession)">重命名</a-button>
            <a-button v-if="chat.currentSession" size="small" @click="togglePin(chat.currentSession)">
              {{ chat.currentSession.is_pinned ? "取消置顶" : "置顶" }}
            </a-button>
            <a-popconfirm v-if="chat.currentSession" content="确认删除当前会话？" @ok="deleteSession(chat.currentSession)">
              <a-button size="small" status="danger">删除</a-button>
            </a-popconfirm>
          </div>
        </div>
        <section class="last-request-state" data-testid="last-request-state">
          <header>
            <strong>最后一次请求</strong>
            <a-tag>{{ lastRequestStatusText }}</a-tag>
          </header>
          <div class="trace-grid">
            <span>scope: {{ lastRequestList(lastRequestState.knowledge_base_ids) }}</span>
            <span>files: {{ lastRequestList(lastRequestState.knowledge_ids) }}</span>
            <span>mode: {{ lastRequestState.mode || "-" }}</span>
            <span>top_k: {{ lastRequestState.top_k || "-" }}</span>
            <span>hit_count: {{ lastRequestState.hit_count ?? "-" }}</span>
            <span>耗时: {{ lastRequestDuration(lastRequestState.duration_ms) }}</span>
          </div>
          <a-alert v-if="lastRequestState.error_message" type="warning" :content="String(lastRequestState.error_message)" />
        </section>
        <a-alert
          v-if="rerankBlockedByKb"
          type="warning"
          content="当前知识库未启用重排。请到知识库列表点击“编辑配置”，打开该知识库的 rerank 索引策略。"
          show-icon
        />
        <!-- MentionSelector: knowmate 当前用显式选择器复刻 WeKnora @ KB/file scope。 -->
        <section class="mention-scope-panel">
          <div class="mention-scope-header">
            <div>
              <strong>引用范围</strong>
              <span>默认使用当前知识库，可追加 KB 或文件范围。</span>
            </div>
            <a-button size="small" @click="clearMentionScope">清除范围</a-button>
          </div>
          <div class="mention-scope-controls">
            <a-select v-model="selectedMentionKbIds" multiple allow-clear placeholder="选择 KB scope">
              <a-option v-for="kb in kbStore.knowledgeBases" :key="kb.id" :value="kb.id">
                {{ kb.name }} · {{ kb.kb_type === "faq" ? "FAQ" : "文档" }}
              </a-option>
            </a-select>
            <a-select v-model="selectedMentionDocumentIds" multiple allow-clear placeholder="选择当前 KB 文件">
              <a-option v-for="document in kbStore.documents" :key="document.id" :value="document.id">
                {{ document.title }}
              </a-option>
            </a-select>
          </div>
          <div class="mention-chip-list">
            <a-tag
              v-for="item in mentionedItems"
              :key="`${item.type}-${item.id}`"
              class="mention-chip"
              :color="item.type === 'kb' ? 'green' : 'gray'"
            >
              {{ item.type === "kb" ? "KB" : "文件" }} · {{ item.name }}
            </a-tag>
            <span v-if="!mentionedItems.length" class="muted-text">默认使用当前单 KB。</span>
          </div>
        </section>

        <div
          ref="messageListRef"
          class="message-list"
          data-testid="chat-message-list"
          @scroll.passive="handleMessageListScroll"
        >
          <section
            v-if="!chat.messages.length && chat.recommendedQuestions.length"
            class="recommended-question-list"
            data-testid="recommended-question-list"
          >
            <header>
              <strong>推荐问题</strong>
              <span>来自当前知识库的 FAQ 和已生成问题</span>
            </header>
            <button
              v-for="item in chat.recommendedQuestions"
              :key="`${item.source_type}-${item.faq_id || item.chunk_id || item.question}`"
              type="button"
              @click="useRecommendedQuestion(item.question)"
            >
              <span>{{ item.question }}</span>
              <small>{{ item.source_type === "faq" ? "FAQ" : item.title || "Chunk" }}</small>
            </button>
          </section>
          <article v-for="message in chat.messages" :key="message.id" class="message" :class="`message--${message.role}`">
            <div v-if="message.role === 'user' && message.mentioned_items?.length" class="message-mentions">
              <a-tag
                v-for="item in message.mentioned_items"
                :key="`${message.id}-${item.type}-${item.id}`"
                :color="item.type === 'kb' ? 'green' : 'gray'"
              >
                {{ item.type === "kb" ? "KB" : "文件" }} · {{ item.name }}
              </a-tag>
            </div>
            <div v-if="message.role === 'user' && message.attachments?.length" class="message-attachments">
              <a-tag
                v-for="attachment in message.attachments"
                :key="`${message.id}-${attachment.filename}`"
                :color="attachment.truncated ? 'orange' : 'blue'"
              >
                临时附件 · {{ attachment.filename }}{{ attachment.truncated ? " · 附件内容已截断" : "" }}
              </a-tag>
            </div>
            <div class="message__bubble">
              <div v-if="message.role === 'assistant'" class="markdown-body" v-html="renderMarkdown(message.content)"></div>
              <p v-else>{{ displayUserContent(message.content) }}</p>
              <a-alert v-if="message.error_message" type="error" :content="message.error_message" />
            </div>
            <a-collapse v-if="message.role === 'assistant' && (message.sources.length || message.retrieval_trace)" :bordered="false">
              <a-collapse-item key="sources" header="引用来源 / 检索过程">
                <div class="trace-panel" data-testid="message-trace">
                  <div class="trace-grid">
                    <span>问题原文: {{ messageTrace(message).query_original || messageTrace(message).original_query || message.original_query || "-" }}</span>
                    <span>问题规范化: {{ messageTrace(message).query_normalized || "-" }}</span>
                    <span>问题改写: {{ messageTrace(message).query_rewritten || messageTrace(message).rewritten_query || message.rewritten_query || "-" }}</span>
                    <span>retrieval_mode: {{ messageTrace(message).retrieval_mode || "-" }}</span>
                    <span>hit_count: {{ messageTrace(message).hit_count ?? message.sources.length }}</span>
                    <span>{{ traceHitSummary(message) }}</span>
                  </div>
                  <section
                    v-if="promptContextSummary(message)"
                    class="prompt-context-summary"
                    data-testid="prompt-context-summary"
                  >
                    <strong>本次送入模型的上下文摘要</strong>
                    <p>{{ promptContextSummary(message) }}</p>
                  </section>
                  <section
                    v-if="selectedContexts(message).length"
                    class="selected-context-list"
                    data-testid="selected-context-list"
                  >
                    <strong>selected_contexts</strong>
                    <article v-for="context in selectedContexts(message)" :key="String(context.chunk_id || context.index)">
                      <header>
                        <span>[{{ traceValueText(context.index) }}] {{ selectedContextTitle(context) }}</span>
                        <a-tag>{{ traceValueText(context.source_type) }}</a-tag>
                      </header>
                      <small>
                        chunk_id: {{ traceValueText(context.chunk_id) }} · parent_chunk_id:
                        {{ traceValueText(context.parent_chunk_id) }} · rerank_score:
                        {{ traceValueText(context.rerank_score) }}
                      </small>
                      <p>{{ traceValueText(context.snippet) }}</p>
                    </article>
                  </section>
                  <div v-if="traceStages(message).length" class="trace-stage-list" data-testid="trace-stage-list">
                    <article v-for="stage in traceStages(message)" :key="String(stage.name)">
                      <header>
                        <strong>{{ traceStageLabel(stage.name) }}</strong>
                        <a-tag :color="traceStatusColor(stage.status)">{{ traceStatusText(stage.status) }}</a-tag>
                      </header>
                      <span>{{ stage.duration_ms ?? 0 }} ms</span>
                      <small>{{ traceStageSummary(stage) }}</small>
                    </article>
                  </div>
                  <div v-if="message.sources.length" class="source-list">
                    <SourceCard v-for="source in message.sources" :key="source.chunk_id" :source="source" />
                  </div>
                </div>
              </a-collapse-item>
            </a-collapse>
          </article>
          <a-empty v-if="!chat.messages.length && !chat.recommendedQuestions.length" description="暂无消息" />
        </div>

        <div class="chat-input">
          <div class="chat-input__box">
            <div v-if="mentionedItems.length || chatAttachments.length" class="composer-chip-row">
              <a-tag
                v-for="item in mentionedItems"
                :key="`composer-${item.type}-${item.id}`"
                :color="item.type === 'kb' ? 'green' : 'gray'"
              >
                {{ item.type === "kb" ? "KB" : "文件" }} · {{ item.name }}
              </a-tag>
              <a-tag
                v-for="attachment in chatAttachments"
                :key="`composer-${attachment.filename}`"
                :color="attachment.truncated ? 'orange' : 'blue'"
                closable
                @close="removeAttachment(attachment.filename)"
              >
                附件 · {{ attachment.filename }}{{ attachment.truncated ? " · 已截断" : "" }}
              </a-tag>
            </div>
            <a-textarea
              v-model="chat.question"
              data-testid="question"
              :auto-size="{ minRows: 3, maxRows: 8 }"
              placeholder="向知友提问，Ctrl + Enter 发送"
              @keydown.ctrl.enter.prevent="askQuestion"
            />
            <a-alert
              v-if="chatAttachments.some((attachment) => attachment.truncated)"
              type="warning"
              content="附件内容已截断，将只作为本轮临时上下文使用。"
            />
            <div class="chat-input__footer">
              <div class="chat-attachment-panel">
                <input
                  ref="attachmentInput"
                  data-testid="chat-attachment-input"
                  type="file"
                  multiple
                  :accept="acceptedAttachmentTypes"
                  @change="handleAttachmentChange"
                />
                <a-select v-model="selectedKbId" class="composer-kb-select" placeholder="全部知识库">
                  <a-option v-for="kb in kbStore.knowledgeBases" :key="kb.id" :value="kb.id">
                    {{ kb.name }}
                  </a-option>
                </a-select>
                <a-button size="small" class="composer-tool" @click="enableQueryRewrite = !enableQueryRewrite">
                  快速
                </a-button>
                <a-button size="small" class="composer-tool" @click="attachmentInput?.click()">图片</a-button>
              </div>
              <div class="chat-input__actions">
                <a-button
                  type="primary"
                  shape="circle"
                  class="send-button"
                  data-testid="ask-question"
                  :loading="chat.answering"
                  :disabled="!selectedKbId || !chat.question.trim() || Boolean(rerankBlockedByKb)"
                  @click="askQuestion"
                >
                  ↑
                </a-button>
                <a-button
                  v-if="chat.answering"
                  data-testid="stop-generation"
                  status="warning"
                  @click="stopGeneration"
                >
                  停止生成
                </a-button>
              </div>
            </div>
          </div>
        </div>

        <a-collapse class="search-debug" data-testid="knowledge-search-panel">
          <a-collapse-item key="search" header="检索调试">
            <div class="qa-layout">
              <div class="qa-layout__input">
                <a-input v-model="chat.knowledgeSearchQuery" data-testid="knowledge-search-query" placeholder="输入检索 query" />
                <a-button
                  type="primary"
                  data-testid="run-knowledge-search"
                  :loading="chat.searchingKnowledge"
                  :disabled="!selectedKbId || !chat.knowledgeSearchQuery.trim() || Boolean(rerankBlockedByKb)"
                  @click="searchKnowledge"
                >
                  只检索来源
                </a-button>
              </div>
              <div class="qa-layout__result" data-testid="knowledge-search-result">
                <div
                  v-if="knowledgeSearchTraceStages().length"
                  class="trace-stage-list trace-stage-list--debug"
                  data-testid="knowledge-search-trace"
                >
                  <article v-for="stage in knowledgeSearchTraceStages()" :key="`search-${stage.name}`">
                    <header>
                      <strong>{{ traceStageLabel(stage.name) }}</strong>
                      <a-tag :color="traceStatusColor(stage.status)">{{ traceStatusText(stage.status) }}</a-tag>
                    </header>
                    <span>{{ stage.duration_ms ?? 0 }} ms</span>
                    <small>{{ traceStageSummary(stage) }}</small>
                  </article>
                </div>
                <div v-if="chat.knowledgeSearchResult?.hits.length" class="source-list">
                  <SourceCard v-for="hit in chat.knowledgeSearchResult.hits" :key="hit.chunk_id" :source="hit" />
                </div>
                <a-empty v-else description="暂无命中来源" />
              </div>
            </div>
          </a-collapse-item>
        </a-collapse>
      </section>
    </section>

    <a-modal v-model:visible="renameVisible" title="重命名会话" :on-before-ok="submitRename">
      <a-input v-model="renameTitle" />
    </a-modal>
  </main>
</template>

<style scoped>
.chat-page {
  min-height: 100vh;
  padding: 20px 20px 0 0;
  background: #f4f5f7;
}

.chat-workbench {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  height: calc(100vh - 20px);
  min-height: 720px;
  border: 1px solid #e8eaee;
  border-radius: 26px 26px 0 0;
  overflow: hidden;
  background: #ffffff;
  box-shadow: 0 10px 34px rgba(24, 30, 38, 0.04);
}

.chat-sidebar {
  display: none;
  grid-template-rows: auto auto minmax(0, 1fr);
  border-right: 1px solid var(--km-border);
  background: #f8faf9;
}

.chat-sidebar__top {
  display: grid;
  gap: 10px;
  padding: 14px;
  border-bottom: 1px solid var(--km-border);
}

.session-batch-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  color: var(--km-text-secondary);
  font-size: 12px;
}

.history-search-panel {
  display: grid;
  gap: 10px;
  padding: 12px 14px;
  border-bottom: 1px solid var(--km-border);
  background: #ffffff;
}

.history-search-panel header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}

.history-search-panel header span {
  color: var(--km-text-secondary);
  font-size: 12px;
}

.history-search-results {
  display: grid;
  gap: 8px;
  max-height: 260px;
  overflow: auto;
}

.history-search-results button {
  display: grid;
  gap: 4px;
  border: 1px solid var(--km-border);
  border-radius: 6px;
  padding: 9px 10px;
  color: var(--km-text-primary);
  background: var(--km-bg-card);
  text-align: left;
  cursor: pointer;
}

.history-search-results button:hover {
  border-color: #bfead6;
  background: var(--km-bg-deep);
}

.history-search-results span,
.history-search-results small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-search-results small {
  color: var(--km-text-secondary);
}

.session-list {
  display: grid;
  align-content: start;
  gap: 4px;
  padding: 10px 8px;
  overflow: auto;
}

.session-item {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 8px;
  align-items: start;
  width: 100%;
  border: 1px solid transparent;
  border-radius: 6px;
  padding: 9px 10px;
  color: var(--km-text-primary);
  background: transparent;
}

.session-item button {
  display: grid;
  gap: 4px;
  min-width: 0;
  border: 0;
  padding: 0;
  color: inherit;
  background: transparent;
  text-align: left;
  cursor: pointer;
}

.session-item:hover,
.session-item--active {
  border-color: rgba(22, 199, 132, 0.18);
  background: rgba(22, 199, 132, 0.08);
}

.session-item span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-item small,
.setting-label {
  color: var(--km-text-secondary);
  font-size: 12px;
}

.recommended-question-list {
  display: grid;
  gap: 10px;
  width: min(760px, 100%);
  margin: 0 auto;
}

.recommended-question-list header {
  display: flex;
  align-items: baseline;
  gap: 10px;
  color: var(--km-text-primary);
}

.recommended-question-list header span {
  color: var(--km-text-secondary);
  font-size: 12px;
}

.recommended-question-list button {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border: 1px solid var(--km-border);
  border-radius: 6px;
  padding: 11px 13px;
  color: var(--km-text-primary);
  background: var(--km-bg-card);
  text-align: left;
  cursor: pointer;
}

.recommended-question-list button:hover {
  border-color: #bfead6;
  background: var(--km-bg-deep);
}

.recommended-question-list small {
  flex: 0 0 auto;
  color: var(--km-text-secondary);
  font-size: 12px;
}

.chat-main {
  display: grid;
  grid-template-rows: auto auto auto auto minmax(0, 1fr) auto auto;
  min-width: 0;
  min-height: 0;
  background: #ffffff;
}

.chat-session-header {
  padding: 22px 28px 12px;
}

.chat-session-header h1 {
  color: #070a0f;
  font-size: 24px;
  font-weight: 800;
  line-height: 1.3;
}

.chat-toolbar {
  display: none;
  grid-template-columns: minmax(360px, 1fr) auto;
  gap: 12px;
  align-items: start;
  padding: 14px 18px;
  border-bottom: 1px solid var(--km-border);
  background: #ffffff;
}

.chat-toolbar__primary {
  display: grid;
  grid-template-columns: minmax(260px, 420px) minmax(0, 1fr);
  gap: 12px;
  align-items: center;
  min-width: 0;
}

.kb-select-item {
  margin-bottom: 0;
}

.chat-toolbar__meta {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.chat-toolbar__meta strong,
.chat-toolbar__meta span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-toolbar__meta strong {
  color: var(--km-text-primary);
  font-size: 14px;
}

.chat-toolbar__meta span {
  color: var(--km-text-secondary);
  font-size: 12px;
}

.chat-toolbar__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
}

.mention-scope-panel {
  display: none;
  gap: 10px;
  border-bottom: 1px solid var(--km-border);
  padding: 12px 18px;
  background: #fbfdfc;
}

.mention-scope-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.mention-scope-header div {
  display: grid;
  gap: 3px;
}

.mention-scope-header strong {
  font-size: 14px;
}

.mention-scope-header span {
  color: var(--km-text-secondary);
  font-size: 12px;
}

.last-request-state {
  display: none;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 8px 14px;
  align-items: center;
  border-bottom: 1px solid var(--km-border);
  padding: 10px 18px;
  background: #ffffff;
}

.last-request-state header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.mention-scope-controls {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.mention-chip-list,
.message-mentions,
.message-attachments,
.composer-chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.mention-chip {
  max-width: 220px;
}

.message-list {
  display: grid;
  align-content: start;
  gap: 28px;
  min-height: 0;
  padding: 26px clamp(32px, 13vw, 240px) 120px;
  overflow: auto;
  overscroll-behavior: contain;
  scroll-padding-bottom: 120px;
  background: #ffffff;
}

.message {
  display: grid;
  gap: 10px;
  width: min(1000px, 100%);
  max-width: 100%;
  color: #2d3137;
  font-size: 18px;
  line-height: 1.8;
}

.message--user {
  justify-self: end;
  width: min(990px, 82%);
  max-width: 990px;
}

.message--assistant {
  justify-self: start;
  width: min(1080px, 100%);
}

.message__bubble {
  border: 0;
  border-radius: 20px;
  padding: 18px 20px;
  background: var(--km-bg-card);
}

.message--assistant .message__bubble {
  border-color: transparent;
  padding: 0;
  background: transparent;
}

.message--user .message__bubble {
  background: #f2f2f2;
}

.message__role {
  display: none;
  margin-bottom: 6px;
  color: var(--km-text-secondary);
  font-size: 12px;
  font-weight: 600;
}

.message--user .message__role {
  text-align: right;
}

.message__bubble p {
  margin: 0;
  white-space: pre-wrap;
  line-height: 1.75;
}

.message .markdown-body {
  color: #2b2f35;
  font-size: 18px;
  line-height: 1.85;
}

.message .markdown-body :deep(h1),
.message .markdown-body :deep(h2),
.message .markdown-body :deep(h3) {
  margin: 24px 0 10px;
  color: #171a20;
  font-weight: 800;
  line-height: 1.45;
}

.message .markdown-body :deep(h1) {
  font-size: 24px;
}

.message .markdown-body :deep(h2),
.message .markdown-body :deep(h3) {
  font-size: 22px;
}

.message .markdown-body :deep(ul),
.message .markdown-body :deep(ol) {
  padding-left: 28px;
}

.message .markdown-body :deep(li) {
  margin: 10px 0;
}

.message :deep(.arco-collapse) {
  width: min(760px, 100%);
  border: 1px solid var(--km-border);
  border-radius: 6px;
  overflow: hidden;
  background: #ffffff;
  box-shadow: 0 2px 4px rgba(7, 192, 95, 0.06);
}

.message :deep(.arco-collapse-item-header) {
  min-height: 34px;
  padding: 7px 12px;
  color: var(--km-text-primary);
  font-size: 12px;
  font-weight: 600;
}

.message :deep(.arco-collapse-item-content-box) {
  padding: 10px 12px 12px;
}

.trace-panel,
.source-list {
  display: grid;
  gap: 12px;
}

.prompt-context-summary {
  display: grid;
  gap: 6px;
  border: 1px solid var(--km-border);
  border-radius: 6px;
  padding: 10px;
  background: #fbfdfc;
}

.prompt-context-summary p {
  margin: 0;
  color: var(--km-text-secondary);
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
}

.selected-context-list {
  display: grid;
  gap: 8px;
  border: 1px solid var(--km-border);
  border-radius: 6px;
  padding: 10px;
  background: #fbfdfc;
}

.selected-context-list article {
  display: grid;
  gap: 4px;
  border-top: 1px solid var(--km-border);
  padding-top: 8px;
}

.selected-context-list article:first-of-type {
  border-top: 0;
  padding-top: 0;
}

.selected-context-list header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.selected-context-list small,
.selected-context-list p {
  margin: 0;
  color: var(--km-text-secondary);
  font-size: 12px;
  line-height: 1.6;
}

.trace-stage-list {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}

.trace-stage-list article {
  display: grid;
  gap: 4px;
  border: 1px solid var(--km-border);
  border-radius: 6px;
  padding: 8px;
  background: var(--km-bg-card);
}

.trace-stage-list article header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.trace-stage-list small {
  color: var(--km-text-secondary);
  line-height: 1.5;
}

.trace-stage-list--debug {
  margin-bottom: 12px;
}

.trace-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 12px;
  color: var(--km-text-secondary);
  font-size: 12px;
}

.last-request-state .trace-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.last-request-state .trace-grid span {
  max-width: 240px;
  border: 1px solid #eef0f2;
  border-radius: 4px;
  padding: 3px 7px;
  overflow: hidden;
  background: #fbfdfc;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-input {
  border-top: 0;
  padding: 0 28px 28px;
  background: #ffffff;
}

.chat-input__box {
  display: grid;
  gap: 12px;
  width: min(1210px, 100%);
  margin: 0 auto;
  border: 1px solid #e5e7eb;
  border-radius: 30px;
  padding: 22px 26px 20px;
  background: #ffffff;
  box-shadow: 0 12px 30px rgba(31, 35, 41, 0.1);
}

.chat-input__box :deep(.arco-textarea-wrapper) {
  border: 0;
  padding: 0;
  background: transparent;
  box-shadow: none;
}

.chat-input__box :deep(textarea) {
  min-height: 44px;
  color: #242830;
  font-size: 18px;
  line-height: 1.7;
}

.chat-input__box :deep(textarea::placeholder) {
  color: #c5cad2;
}

.chat-input__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border-top: 0;
  padding-top: 0;
}

.chat-attachment-panel {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 18px;
  min-width: 0;
}

.chat-attachment-panel input {
  display: none;
}

.chat-input__actions {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 8px;
}

.composer-kb-select {
  width: 160px;
}

.composer-kb-select :deep(.arco-select-view-single) {
  border: 0;
  padding-left: 0;
  background: transparent;
  color: #20242b;
  font-size: 16px;
}

.composer-tool {
  border: 0;
  padding: 0;
  color: #20242b;
  background: transparent;
  font-size: 16px;
}

.composer-tool:hover {
  color: #0eaf69;
  background: transparent;
}

.send-button {
  width: 40px;
  height: 40px;
  border: 0;
  color: #ffffff;
  background: #abeecb;
  font-size: 24px;
  font-weight: 700;
}

.send-button:not(.arco-btn-disabled):hover {
  background: #8fe6ba;
}

.search-debug {
  display: none;
  border-top: 1px solid var(--km-border);
  background: #ffffff;
}

@media (max-width: 980px) {
  .chat-workbench,
  .chat-toolbar,
  .chat-toolbar__primary,
  .last-request-state,
  .trace-grid {
    grid-template-columns: 1fr;
  }

  .chat-workbench {
    height: auto;
    min-height: calc(100vh - 16px);
    border-radius: 18px 18px 0 0;
  }

  .chat-sidebar {
    min-height: 220px;
    border-right: 0;
    border-bottom: 1px solid var(--km-border);
  }

  .chat-toolbar__actions {
    justify-content: flex-start;
  }

  .mention-scope-controls,
  .trace-stage-list {
    grid-template-columns: 1fr;
  }

  .message {
    font-size: 15px;
    max-width: 100%;
  }

  .message--user {
    width: 100%;
    max-width: 100%;
  }

  .message-list {
    padding: 18px 16px 48px;
  }

  .chat-input__footer {
    align-items: stretch;
    flex-direction: column;
  }

  .chat-input__actions {
    justify-content: flex-end;
  }
}
</style>
