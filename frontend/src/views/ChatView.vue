<script setup lang="ts">
import MarkdownIt from "markdown-it";
import hljs from "highlight.js";
import { Message } from "@arco-design/web-vue";
import { computed, onMounted, ref } from "vue";
import SourceCard from "../components/SourceCard.vue";
import { useChatStore } from "../stores/chat";
import { useKnowledgeBaseStore } from "../stores/knowledgeBase";
import { useRetrievalStore } from "../stores/retrieval";
import { formatApiError } from "../utils/api";

const chat = useChatStore();
const kbStore = useKnowledgeBaseStore();
const retrieval = useRetrievalStore();
const selectedKbId = ref("");

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

const renderedAnswer = computed(() => (chat.quickAnswer?.answer ? md.render(chat.quickAnswer.answer) : ""));

function requestParams() {
  return {
    knowledge_base_id: selectedKbId.value,
    top_k: Number(retrieval.retrievalRerankTopK || 10),
    mode: retrieval.retrievalMode,
    enable_rerank: retrieval.retrievalEnableRerank,
  };
}

async function askQuestion() {
  try {
    await chat.askQuestion(requestParams());
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

async function searchKnowledge() {
  try {
    await chat.searchKnowledge(requestParams());
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

onMounted(() => {
  Promise.all([kbStore.loadKnowledgeBases(), retrieval.loadRetrievalConfig()]).then(() => {
    selectedKbId.value = kbStore.knowledgeBases[0]?.id || "";
  }).catch((error) => {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  });
});
</script>

<template>
  <main class="page-shell">
    <a-page-header title="快速问答" subtitle="选择知识库后进行 quick-answer，回答和来源依据分开展示。" />

    <section class="content-card">
      <a-form-item label="知识库">
        <a-select v-model="selectedKbId" placeholder="请选择知识库" data-testid="knowledge-base-select">
          <a-option v-for="kb in kbStore.knowledgeBases" :key="kb.id" :value="kb.id">
            {{ kb.name }} · {{ kb.document_count }} 文档 · {{ kb.chunk_count }} chunks
          </a-option>
        </a-select>
      </a-form-item>
    </section>

    <section class="content-card">
      <a-tabs default-active-key="answer">
        <a-tab-pane key="answer" title="快速问答">
          <div class="qa-layout">
            <div class="qa-layout__input">
              <a-textarea
                v-model="chat.question"
                data-testid="question"
                :auto-size="{ minRows: 5, maxRows: 10 }"
                placeholder="请输入问题"
              />
              <a-button
                type="primary"
                data-testid="ask-question"
                :loading="chat.answering"
                :disabled="!selectedKbId || !chat.question.trim()"
                @click="askQuestion"
              >
                提问
              </a-button>
            </div>
            <div class="qa-layout__result">
              <article v-if="chat.quickAnswer" class="answer-result" data-testid="answer-result">
                <h2>回答</h2>
                <div class="markdown-body" v-html="renderedAnswer"></div>
                <h2>来源依据</h2>
                <div v-if="chat.quickAnswer.sources.length" class="source-list">
                  <SourceCard v-for="source in chat.quickAnswer.sources" :key="source.chunk_id" :source="source" />
                </div>
                <a-empty v-else description="暂无来源" />
              </article>
              <a-empty v-else description="暂无回答" />
            </div>
          </div>
        </a-tab-pane>

        <a-tab-pane key="search" title="知识搜索">
          <div class="qa-layout">
            <div class="qa-layout__input" data-testid="knowledge-search-panel">
              <a-input v-model="chat.knowledgeSearchQuery" data-testid="knowledge-search-query" placeholder="输入检索 query" />
              <a-button
                type="primary"
                data-testid="run-knowledge-search"
                :loading="chat.searchingKnowledge"
                :disabled="!selectedKbId || !chat.knowledgeSearchQuery.trim()"
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
        </a-tab-pane>
      </a-tabs>
    </section>
  </main>
</template>
