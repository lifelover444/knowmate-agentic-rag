<script setup lang="ts">
import { Message } from "@arco-design/web-vue";
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import DocumentUpload from "../components/DocumentUpload.vue";
import { useKnowledgeBaseStore } from "../stores/knowledgeBase";
import { formatApiError } from "../utils/api";
import type { DocumentRead } from "../types/api";

const route = useRoute();
const router = useRouter();
const kbStore = useKnowledgeBaseStore();
const drawerVisible = ref(false);
const importVisible = ref(false);
const importMode = ref<"text" | "url">("text");
const activeDocument = ref<DocumentRead | null>(null);
const kbId = computed(() => String(route.params.kbId || ""));
const filters = ref({ status: "", file_type: "", keyword: "" });
const importForm = ref({ title: "", content: "", format: "markdown", url: "" });

function statusColor(status: string) {
  return (
    {
      pending: "orange",
      processing: "blue",
      completed: "green",
      failed: "red",
    }[status] || "gray"
  );
}

function statusText(status: string) {
  return (
    {
      pending: "等待解析",
      processing: "解析中",
      completed: "解析完成",
      failed: "解析失败",
    }[status] || status
  );
}

async function refresh() {
  await Promise.all([kbStore.loadKnowledgeBase(kbId.value), kbStore.loadDocuments(kbId.value, filters.value), kbStore.loadTasks({ knowledge_base_id: kbId.value })]);
}

async function upload(file: File) {
  try {
    const document = await kbStore.uploadDocument(kbId.value, file);
    Message.success("文档已上传，开始解析");
    await kbStore.pollDocument(document.id);
    Message.success("文档解析完成");
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

async function openChunks(document: DocumentRead) {
  activeDocument.value = document;
  kbStore.currentDocument = document;
  drawerVisible.value = true;
  try {
    await kbStore.loadChunks(document.id);
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

async function reprocess(document: DocumentRead) {
  try {
    const next = await kbStore.reprocessDocument(document.id);
    Message.success("文档已提交重新处理");
    await kbStore.pollDocument(next.id);
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

async function deleteDocument(document: DocumentRead) {
  try {
    kbStore.currentDocument = document;
    await kbStore.deleteDocument(document.id);
    Message.success("文档已删除");
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

async function reprocessKb() {
  try {
    await kbStore.reprocessKnowledgeBase(kbId.value);
    Message.success("知识库已提交重建");
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

function checked(documentId: string) {
  return kbStore.selectedDocumentIds.includes(documentId);
}

function toggleSelected(documentId: string, value: boolean) {
  kbStore.selectedDocumentIds = value
    ? Array.from(new Set([...kbStore.selectedDocumentIds, documentId]))
    : kbStore.selectedDocumentIds.filter((id) => id !== documentId);
}

async function batchReprocess() {
  try {
    await kbStore.batchReprocessDocuments(kbId.value, kbStore.selectedDocumentIds);
    Message.success("已批量提交重新处理");
    await refresh();
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

async function batchDelete() {
  try {
    await kbStore.batchDeleteDocuments(kbId.value, kbStore.selectedDocumentIds);
    Message.success("已批量删除文档");
    await refresh();
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

function openImport(mode: "text" | "url") {
  importMode.value = mode;
  importForm.value = { title: "", content: "", format: "markdown", url: "" };
  importVisible.value = true;
}

async function submitImport() {
  try {
    const document = importMode.value === "url"
      ? await kbStore.importUrl(kbId.value, { url: importForm.value.url })
      : await kbStore.importText(kbId.value, {
        title: importForm.value.title,
        content: importForm.value.content,
        format: importForm.value.format,
      });
    importVisible.value = false;
    Message.success("内容已导入，进入任务中心处理");
    await kbStore.pollDocument(document.id);
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

onMounted(() => {
  refresh().then(() => {
    kbStore.documents
      .filter((document) => document.parse_status === "pending" || document.parse_status === "processing")
      .forEach((document) => {
        kbStore.pollDocument(document.id).catch(() => null);
      });
  }).catch((error) => {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  });
});
</script>

<template>
  <main class="page-shell">
    <a-page-header
      :title="kbStore.currentKb?.name || '文档管理'"
      :subtitle="kbStore.currentKb?.description || '上传、解析、查看 chunks，并支持文档和知识库重处理。'"
      @back="router.push('/knowledge-bases')"
    >
      <template #extra>
        <a-space>
          <a-button @click="router.push(`/knowledge-bases/${kbId}/faqs`)">FAQ</a-button>
          <a-button @click="openImport('text')">在线文本</a-button>
          <a-button @click="openImport('url')">URL 导入</a-button>
          <a-popconfirm content="确认重建整个知识库？" type="warning" @ok="reprocessKb">
            <a-button data-testid="reprocess-kb" :loading="kbStore.reprocessing">重建知识库</a-button>
          </a-popconfirm>
        </a-space>
      </template>
    </a-page-header>

    <section class="content-card">
      <DocumentUpload :uploading="kbStore.uploading" :polling="kbStore.polling" @upload="upload" />
    </section>

    <section class="content-card">
      <div class="section-heading">
        <div>
          <h2>文档列表</h2>
          <p>筛选、批量处理、任务状态和失败原因保持可见。</p>
        </div>
        <a-space>
          <a-button :disabled="!kbStore.selectedDocumentIds.length" @click="batchReprocess">批量重处理</a-button>
          <a-popconfirm content="确认批量删除选中文档？" @ok="batchDelete">
            <a-button status="danger" :disabled="!kbStore.selectedDocumentIds.length">批量删除</a-button>
          </a-popconfirm>
        </a-space>
      </div>
      <div class="form-grid form-grid--compact">
        <a-form-item label="状态">
          <a-select v-model="filters.status" allow-clear @change="refresh">
            <a-option value="pending">等待解析</a-option>
            <a-option value="processing">解析中</a-option>
            <a-option value="completed">解析完成</a-option>
            <a-option value="failed">解析失败</a-option>
          </a-select>
        </a-form-item>
        <a-form-item label="文件类型"><a-input v-model="filters.file_type" placeholder="txt / md / pdf" @change="refresh" /></a-form-item>
        <a-form-item label="关键字"><a-input-search v-model="filters.keyword" search-button placeholder="标题或文件名" @search="refresh" /></a-form-item>
      </div>
      <a-table :data="kbStore.documents" :pagination="false" row-key="id">
        <template #columns>
          <a-table-column title="选择" :width="70">
            <template #cell="{ record }">
              <a-checkbox :model-value="checked(record.id)" @change="(value) => toggleSelected(record.id, Boolean(value))" />
            </template>
          </a-table-column>
          <a-table-column title="文档" data-index="title" />
          <a-table-column title="来源">
            <template #cell="{ record }">
              <div class="table-stack">
                <span>{{ record.source_type }}</span>
                <span>{{ record.file_name || record.source }}</span>
              </div>
            </template>
          </a-table-column>
          <a-table-column title="状态">
            <template #cell="{ record }">
              <a-tag :color="statusColor(record.parse_status)">{{ statusText(record.parse_status) }}</a-tag>
              <a-tag v-if="record.task_status" color="blue">{{ record.task_status }}</a-tag>
              <p v-if="record.error_message" class="inline-error">{{ record.error_message }}</p>
            </template>
          </a-table-column>
          <a-table-column title="索引">
            <template #cell="{ record }">
              <div class="table-stack">
                <span>{{ record.chunk_count }} chunks</span>
                <span>{{ record.embedding_model_id || "-" }}</span>
              </div>
            </template>
          </a-table-column>
          <a-table-column title="操作">
            <template #cell="{ record }">
              <a-space>
                <a-button size="mini" @click="openChunks(record)">查看 chunks</a-button>
                <a-button size="mini" data-testid="reprocess-doc" @click="reprocess(record)">重新处理</a-button>
                <a-popconfirm content="确认删除这个文档？" type="warning" @ok="deleteDocument(record)">
                  <a-button size="mini" status="danger">删除</a-button>
                </a-popconfirm>
              </a-space>
            </template>
          </a-table-column>
        </template>
      </a-table>
      <a-empty v-if="!kbStore.documents.length" description="暂无文档" />
    </section>

    <a-drawer v-model:visible="drawerVisible" :width="680" :title="activeDocument?.title || '文档 chunks'">
      <div v-if="kbStore.chunks.length" class="chunk-list" data-testid="chunks-list">
        <article v-for="chunk in kbStore.chunks" :key="chunk.id" class="chunk-item">
          <header>
            <strong>#{{ chunk.chunk_index }}</strong>
            <a-tag color="green">{{ chunk.chunk_type }}</a-tag>
          </header>
          <small v-if="chunk.context_header">{{ chunk.context_header }}</small>
          <small v-if="chunk.parent_chunk_id">parent_chunk_id: {{ chunk.parent_chunk_id }}</small>
          <small v-if="chunk.metadata">metadata: {{ chunk.metadata }}</small>
          <p>{{ chunk.content }}</p>
        </article>
      </div>
      <a-empty v-else description="暂无切片" />
    </a-drawer>

    <a-modal v-model:visible="importVisible" :title="importMode === 'url' ? 'URL 导入' : '在线文本导入'" @ok="submitImport">
      <div v-if="importMode === 'url'" class="modal-form">
        <a-alert type="info" content="URL 导入仅抓取 HTML title 和可读正文，本地与内网地址会被拒绝。" />
        <a-form-item label="URL"><a-input v-model="importForm.url" placeholder="https://example.com/article" /></a-form-item>
      </div>
      <div v-else class="modal-form">
        <a-form-item label="标题"><a-input v-model="importForm.title" /></a-form-item>
        <a-form-item label="格式">
          <a-radio-group v-model="importForm.format" type="button">
            <a-radio value="markdown">Markdown</a-radio>
            <a-radio value="text">纯文本</a-radio>
          </a-radio-group>
        </a-form-item>
        <a-form-item label="内容"><a-textarea v-model="importForm.content" :auto-size="{ minRows: 8, maxRows: 14 }" /></a-form-item>
      </div>
    </a-modal>
  </main>
</template>
