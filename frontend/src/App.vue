<script setup>
import {
  BookOpen,
  CheckCircle2,
  FileText,
  Loader2,
  MessageSquareText,
  Play,
  Search,
  UploadCloud,
} from "lucide-vue-next";
import { computed, ref } from "vue";

const apiBase = "/api/v1";
const kbName = ref(`知友测试知识库-${new Date().toLocaleTimeString("zh-CN", { hour12: false })}`);
const kbDescription = ref("用于验证知识库创建、文档上传、切片入库、向量检索和快速问答的测试知识库。");
const knowledgeBase = ref(null);
const documentRecord = ref(null);
const chunks = ref([]);
const selectedFile = ref(null);
const question = ref("知友能做什么？");
const quickAnswer = ref(null);
const busy = ref(false);
const uploading = ref(false);
const polling = ref(false);
const answering = ref(false);
const errorMessage = ref("");
const eventLog = ref([]);

const pipeline = computed(() => [
  { label: "知识库", done: Boolean(knowledgeBase.value), active: busy.value },
  { label: "上传", done: Boolean(documentRecord.value), active: uploading.value },
  {
    label: "解析",
    done: documentRecord.value?.parse_status === "completed",
    active: polling.value && documentRecord.value?.parse_status !== "completed",
  },
  { label: "切片入库", done: chunks.value.length > 0, active: false },
  { label: "问答", done: Boolean(quickAnswer.value?.answer), active: answering.value },
]);

function log(message) {
  eventLog.value.unshift(`${new Date().toLocaleTimeString("zh-CN", { hour12: false })} ${message}`);
  eventLog.value = eventLog.value.slice(0, 8);
}

function handleError(error) {
  errorMessage.value = error instanceof Error ? error.message : String(error);
}

function statusText(status) {
  return (
    {
      pending: "等待解析",
      processing: "解析中",
      completed: "解析完成",
      failed: "解析失败",
      enabled: "已启用",
      disabled: "已停用",
    }[status] || status
  );
}

async function request(path, options = {}) {
  const response = await fetch(`${apiBase}${path}`, options);
  const text = await response.text();
  const payload = text ? JSON.parse(text) : null;
  if (!response.ok) {
    throw new Error(payload?.detail || `HTTP ${response.status}`);
  }
  return payload;
}

async function createKnowledgeBase() {
  busy.value = true;
  errorMessage.value = "";
  quickAnswer.value = null;
  chunks.value = [];
  documentRecord.value = null;
  try {
    knowledgeBase.value = await request("/knowledge-bases", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: kbName.value.trim() || "knowmate-test",
        description: kbDescription.value.trim() || null,
      }),
    });
    log(`创建知识库 ${knowledgeBase.value.name}`);
  } catch (error) {
    handleError(error);
  } finally {
    busy.value = false;
  }
}

async function uploadDocument() {
  if (!knowledgeBase.value || !selectedFile.value) return;
  uploading.value = true;
  errorMessage.value = "";
  quickAnswer.value = null;
  chunks.value = [];
  try {
    const formData = new FormData();
    formData.append("file", selectedFile.value);
    documentRecord.value = await request(`/knowledge-bases/${knowledgeBase.value.id}/documents/file`, {
      method: "POST",
      body: formData,
    });
    log(`上传 ${documentRecord.value.file_name || documentRecord.value.title}`);
    await pollDocument();
  } catch (error) {
    handleError(error);
  } finally {
    uploading.value = false;
  }
}

async function pollDocument() {
  if (!documentRecord.value) return;
  polling.value = true;
  try {
    for (let index = 0; index < 45; index += 1) {
      documentRecord.value = await request(`/documents/${documentRecord.value.id}`);
      if (documentRecord.value.parse_status === "completed") {
        log("文档解析完成");
        chunks.value = await request(`/documents/${documentRecord.value.id}/chunks`);
        log(`切片 ${chunks.value.length}`);
        return;
      }
      if (documentRecord.value.parse_status === "failed") {
        throw new Error(documentRecord.value.error_message || "文档解析失败");
      }
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
    throw new Error("文档解析超时");
  } finally {
    polling.value = false;
  }
}

async function askQuestion() {
  if (!knowledgeBase.value || !question.value.trim()) return;
  answering.value = true;
  errorMessage.value = "";
  try {
    quickAnswer.value = await request("/quick-answer", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        knowledge_base_id: knowledgeBase.value.id,
        query: question.value.trim(),
        top_k: 5,
      }),
    });
    log(`返回来源 ${quickAnswer.value.sources.length}`);
  } catch (error) {
    handleError(error);
  } finally {
    answering.value = false;
  }
}
</script>

<template>
  <main class="shell">
    <header class="topbar">
      <div>
        <p class="eyebrow">knowmate知友</p>
        <h1>知识库快速问答测试台</h1>
      </div>
      <div class="health">
        <span class="pulse"></span>
        后端服务 / 向量库
      </div>
    </header>

    <section class="pipeline" aria-label="知识问答链路">
      <div
        v-for="item in pipeline"
        :key="item.label"
        class="step"
        :class="{ done: item.done, active: item.active }"
      >
        <CheckCircle2 v-if="item.done" :size="18" />
        <Loader2 v-else-if="item.active" :size="18" class="spin" />
        <span v-else></span>
        {{ item.label }}
      </div>
    </section>

    <p v-if="errorMessage" class="error" role="alert">{{ errorMessage }}</p>

    <section class="workspace">
      <aside class="panel control-panel">
        <div class="panel-title">
          <BookOpen :size="20" />
          <h2>知识库配置</h2>
        </div>
        <label>
          <span>名称</span>
          <input v-model="kbName" data-testid="kb-name" />
        </label>
        <label>
          <span>描述</span>
          <textarea v-model="kbDescription" data-testid="kb-description" rows="3"></textarea>
        </label>
        <button data-testid="create-kb" :disabled="busy" @click="createKnowledgeBase">
          <Loader2 v-if="busy" :size="17" class="spin" />
          <Play v-else :size="17" />
          创建知识库
        </button>

        <div v-if="knowledgeBase" class="object-block" data-testid="kb-result">
          <strong>{{ knowledgeBase.name }}</strong>
          <small>{{ knowledgeBase.id }}</small>
          <span>{{ knowledgeBase.document_count }} 个文档 / {{ knowledgeBase.chunk_count }} 个切片</span>
        </div>

        <div class="panel-title upload-title">
          <UploadCloud :size="20" />
          <h2>文档上传</h2>
        </div>
        <label class="file-picker">
          <input
            data-testid="file-input"
            type="file"
            accept=".txt,.md,.pdf,.docx"
            :disabled="!knowledgeBase"
            @change="selectedFile = $event.target.files?.[0] || null"
          />
          <span>{{ selectedFile?.name || "选择文件" }}</span>
        </label>
        <button data-testid="upload-doc" :disabled="!knowledgeBase || !selectedFile || uploading" @click="uploadDocument">
          <Loader2 v-if="uploading || polling" :size="17" class="spin" />
          <UploadCloud v-else :size="17" />
          上传并解析
        </button>

        <div v-if="documentRecord" class="object-block" data-testid="doc-result">
          <strong>{{ documentRecord.title }}</strong>
          <small>{{ documentRecord.id }}</small>
          <span class="status" :class="documentRecord.parse_status">{{ statusText(documentRecord.parse_status) }}</span>
        </div>
      </aside>

      <section class="panel chunks-panel">
        <div class="panel-title">
          <FileText :size="20" />
          <h2>文档切片</h2>
        </div>
        <div v-if="chunks.length" class="chunk-list" data-testid="chunks-list">
          <article v-for="chunk in chunks" :key="chunk.id" class="chunk">
            <div>
              <strong>#{{ chunk.chunk_index }}</strong>
              <small>{{ chunk.id }}</small>
            </div>
            <p>{{ chunk.content }}</p>
          </article>
        </div>
        <div v-else class="empty">暂无切片</div>
      </section>

      <section class="panel answer-panel">
        <div class="panel-title">
          <MessageSquareText :size="20" />
          <h2>快速问答</h2>
        </div>
        <label>
          <span>问题</span>
          <textarea v-model="question" data-testid="question" rows="4"></textarea>
        </label>
        <button data-testid="ask-question" :disabled="!knowledgeBase || !question.trim() || answering" @click="askQuestion">
          <Loader2 v-if="answering" :size="17" class="spin" />
          <Search v-else :size="17" />
          提问
        </button>

        <div v-if="quickAnswer" class="answer" data-testid="answer-result">
          <h3>回答</h3>
          <p>{{ quickAnswer.answer }}</p>
          <h3>来源依据</h3>
          <article v-for="source in quickAnswer.sources" :key="source.chunk_id" class="source">
            <strong>{{ source.title || source.document_id }}</strong>
            <small>相似度 {{ source.score.toFixed(4) }}</small>
            <p>{{ source.content }}</p>
          </article>
        </div>
      </section>
    </section>

    <footer class="logline">
      <span v-for="entry in eventLog" :key="entry">{{ entry }}</span>
    </footer>
  </main>
</template>
