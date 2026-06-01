<script setup lang="ts">
import MarkdownIt from "markdown-it";
import hljs from "highlight.js";
import { Message } from "@arco-design/web-vue";
import { computed, onMounted, ref, watch } from "vue";
import SourceCard from "../components/SourceCard.vue";
import { useChatStore } from "../stores/chat";
import { useKnowledgeBaseStore } from "../stores/knowledgeBase";
import { useRetrievalStore } from "../stores/retrieval";
import type { ChatMessageRead, ChatSessionRead, MentionedItem } from "../types/api";
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

function renderMarkdown(content: string): string {
  return md.render(content || "");
}

function shortTime(value: string): string {
  return new Date(value).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
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
  };
}

function clearMentionScope() {
  selectedMentionKbIds.value = [];
  selectedMentionDocumentIds.value = [];
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
  try {
    await chat.askQuestion(requestParams());
    if (chat.streamError) Message.error(chat.streamError);
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

onMounted(() => {
  Promise.all([kbStore.loadKnowledgeBases(), retrieval.loadRetrievalConfig(), chat.loadSessions()]).then(() => {
    selectedKbId.value = chat.currentSession?.knowledge_base_id || kbStore.knowledgeBases[0]?.id || "";
    if (!chat.currentSession && chat.sessions[0]) {
      selectSession(chat.sessions[0]);
    } else if (selectedKbId.value) {
      chat.loadRecommendedQuestions(selectedKbId.value);
    }
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
</script>

<template>
  <main class="page-shell chat-page">
    <a-page-header title="快速问答" subtitle="会话、流式回答、来源依据和检索 trace。" />

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
        <div class="chat-toolbar">
          <a-form-item label="知识库">
            <a-select v-model="selectedKbId" placeholder="请选择知识库" data-testid="knowledge-base-select">
              <a-option v-for="kb in kbStore.knowledgeBases" :key="kb.id" :value="kb.id">
                {{ kb.name }} · {{ kb.document_count }} 文档 · {{ kb.chunk_count }} chunks
              </a-option>
            </a-select>
          </a-form-item>
          <a-space>
            <a-switch v-model="enableQueryRewrite" data-testid="enable-query-rewrite" />
            <span class="setting-label">Query rewrite</span>
            <a-button v-if="chat.currentSession" size="small" @click="openRename(chat.currentSession)">重命名</a-button>
            <a-button v-if="chat.currentSession" size="small" @click="togglePin(chat.currentSession)">
              {{ chat.currentSession.is_pinned ? "取消置顶" : "置顶" }}
            </a-button>
            <a-popconfirm v-if="chat.currentSession" content="确认删除当前会话？" @ok="deleteSession(chat.currentSession)">
              <a-button size="small" status="danger">删除</a-button>
            </a-popconfirm>
          </a-space>
        </div>
        <a-alert
          v-if="rerankBlockedByKb"
          type="warning"
          content="当前知识库未启用重排。请到知识库列表点击“编辑配置”，打开该知识库的 rerank 索引策略。"
          show-icon
        />
        <!-- MentionSelector: knowmate 当前用显式选择器复刻 WeKnora @ KB/file scope。 -->
        <section class="mention-scope-panel">
          <div class="section-heading">
            <div>
              <h2>引用范围</h2>
              <p>选择知识库或当前知识库下的文件，发送时提交 knowledge_base_ids、knowledge_ids 和 mentioned_items。</p>
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

        <div class="message-list" data-testid="chat-message-list">
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
            <div class="message__bubble">
              <div v-if="message.role === 'assistant'" class="markdown-body" v-html="renderMarkdown(message.content)"></div>
              <p v-else>{{ message.content }}</p>
              <a-alert v-if="message.error_message" type="error" :content="message.error_message" />
            </div>
            <a-collapse v-if="message.role === 'assistant' && (message.sources.length || message.retrieval_trace)" :bordered="false">
              <a-collapse-item key="sources" header="来源依据 / Retrieval Trace">
                <div class="trace-panel" data-testid="message-trace">
                  <div class="trace-grid">
                    <span>original_query: {{ messageTrace(message).original_query || message.original_query || "-" }}</span>
                    <span>rewritten_query: {{ messageTrace(message).rewritten_query || message.rewritten_query || "-" }}</span>
                    <span>retrieval_mode: {{ messageTrace(message).retrieval_mode || "-" }}</span>
                    <span>hit_count: {{ messageTrace(message).hit_count ?? message.sources.length }}</span>
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
          <a-textarea
            v-model="chat.question"
            data-testid="question"
            :auto-size="{ minRows: 3, maxRows: 8 }"
            placeholder="请输入问题"
            @keydown.ctrl.enter.prevent="askQuestion"
          />
          <a-button
            type="primary"
            data-testid="ask-question"
            :loading="chat.answering"
            :disabled="!selectedKbId || !chat.question.trim() || Boolean(rerankBlockedByKb)"
            @click="askQuestion"
          >
            发送
          </a-button>
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
  min-height: calc(100vh - 48px);
}

.chat-workbench {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  min-height: 720px;
  border: 1px solid var(--km-border);
  border-radius: var(--km-radius);
  overflow: hidden;
  background: var(--km-bg-card);
}

.chat-sidebar {
  display: grid;
  grid-template-rows: auto 1fr;
  border-right: 1px solid var(--km-border);
  background: #fbfdfc;
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

.session-list {
  display: grid;
  align-content: start;
  gap: 6px;
  padding: 10px;
  overflow: auto;
}

.session-item {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 8px;
  align-items: start;
  width: 100%;
  border: 1px solid transparent;
  border-radius: var(--km-radius);
  padding: 10px;
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
  border-color: #bfead6;
  background: var(--km-bg-deep);
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
  max-width: 720px;
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
  border-radius: var(--km-radius);
  padding: 10px 12px;
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
  grid-template-rows: auto minmax(360px, 1fr) auto auto;
  min-width: 0;
}

.chat-toolbar,
.chat-input {
  display: grid;
  grid-template-columns: minmax(260px, 1fr) auto;
  gap: 12px;
  align-items: center;
  padding: 14px;
  border-bottom: 1px solid var(--km-border);
}

.mention-scope-panel {
  display: grid;
  gap: 10px;
  border-bottom: 1px solid var(--km-border);
  padding: 14px;
  background: #fbfdfc;
}

.mention-scope-controls {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.mention-chip-list,
.message-mentions {
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
  gap: 16px;
  padding: 18px;
  overflow: auto;
  background: var(--km-bg-page);
}

.message {
  display: grid;
  gap: 10px;
  max-width: 82%;
}

.message--user {
  justify-self: end;
}

.message--assistant {
  justify-self: start;
}

.message__bubble {
  border: 1px solid var(--km-border);
  border-radius: var(--km-radius);
  padding: 12px 14px;
  background: var(--km-bg-card);
}

.message--user .message__bubble {
  border-color: #bfead6;
  background: var(--km-bg-deep);
}

.message__bubble p {
  white-space: pre-wrap;
  line-height: 1.7;
}

.trace-panel,
.source-list {
  display: grid;
  gap: 12px;
}

.trace-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 12px;
  color: var(--km-text-secondary);
  font-size: 12px;
}

.search-debug {
  border-top: 1px solid var(--km-border);
}

@media (max-width: 980px) {
  .chat-workbench,
  .chat-toolbar,
  .chat-input,
  .trace-grid {
    grid-template-columns: 1fr;
  }

  .chat-sidebar {
    min-height: 220px;
    border-right: 0;
    border-bottom: 1px solid var(--km-border);
  }

  .message {
    max-width: 100%;
  }
}
</style>
