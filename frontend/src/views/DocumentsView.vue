<script setup lang="ts">
import { Message } from "@arco-design/web-vue";
import { computed, nextTick, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import DocumentUpload from "../components/DocumentUpload.vue";
import { DocumentProcessingTimeoutError, useKnowledgeBaseStore } from "../stores/knowledgeBase";
import { formatApiError } from "../utils/api";
import type { ChunkRead, DocumentRead, GeneratedQuestion } from "../types/api";

type UploadQueueStatus = "pending" | "uploading" | "queued" | "processing" | "completed" | "failed";

interface UploadQueueItem {
  id: string;
  fileName: string;
  fileSize: number;
  status: UploadQueueStatus;
  documentId?: string;
  taskId?: string;
  errorMessage?: string;
  noticeMessage?: string;
}

const route = useRoute();
const router = useRouter();
const kbStore = useKnowledgeBaseStore();
const drawerVisible = ref(false);
const chunkDetailVisible = ref(false);
const chunkDetailSaving = ref(false);
const generatedQuestionSaving = ref(false);
const timelineVisible = ref(false);
const timelineLoading = ref(false);
const importVisible = ref(false);
const importMode = ref<"text" | "url">("text");
const activeDocument = ref<DocumentRead | null>(null);
const kbId = computed(() => String(route.params.kbId || ""));
const filters = ref({ status: "", file_type: "", keyword: "", tag_id: "" });
const importForm = ref({ title: "", content: "", format: "markdown", url: "", tag_id: "" });
const tagModalVisible = ref(false);
const tagForm = ref({ name: "", color: "#2563eb", sort_order: 0 });
const batchTagVisible = ref(false);
const batchTagId = ref<string>("");
const uploadQueue = ref<UploadQueueItem[]>([]);
const uploadQueueRunning = ref(false);
const moveDocumentVisible = ref(false);
const targetKnowledgeBaseId = ref("");
const movingDocumentIds = ref<string[]>([]);
const chunkForm = ref({
  content: "",
  search_text: "",
  metadataText: "{}",
  is_enabled: true,
  generatedQuestion: "",
});

function statusColor(status: string) {
  return (
    {
      pending: "orange",
      processing: "blue",
      completed: "green",
      failed: "red",
      cancelled: "gray",
    }[status] || "gray"
  );
}

function statusText(status: string) {
  return (
    {
      queued: "等待处理",
      pending: "等待解析",
      processing: "解析中",
      completed: "解析完成",
      failed: "解析失败",
      cancelled: "已取消",
    }[status] || status
  );
}

function uploadQueueStatusText(status: UploadQueueStatus) {
  return (
    {
      pending: "等待上传",
      uploading: "上传中",
      queued: "已入队解析",
      processing: "解析中",
      completed: "解析完成",
      failed: "失败",
    }[status] || status
  );
}

function uploadQueueStatusColor(status: UploadQueueStatus) {
  return (
    {
      pending: "gray",
      uploading: "blue",
      queued: "orange",
      processing: "blue",
      completed: "green",
      failed: "red",
    }[status] || "gray"
  );
}

const uploadQueueSummary = computed(() => {
  const total = uploadQueue.value.length;
  const completed = uploadQueue.value.filter((item) => item.status === "completed").length;
  const failed = uploadQueue.value.filter((item) => item.status === "failed").length;
  const running = uploadQueue.value.filter((item) => ["pending", "uploading", "queued", "processing"].includes(item.status)).length;
  const partial = total > 0 && completed > 0 && failed > 0;
  return { total, completed, failed, running, partial };
});

const moveTargetKnowledgeBases = computed(() => {
  const current = kbStore.currentKb;
  return kbStore.knowledgeBases.filter((kb) => {
    if (!current || kb.id === current.id) return false;
    return kb.kb_type === current.kb_type && kb.embedding_model_id === current.embedding_model_id;
  });
});

const currentChunkGeneratedQuestions = computed<GeneratedQuestion[]>(() => {
  const raw = kbStore.currentChunkDetail?.metadata?.generated_questions;
  if (!Array.isArray(raw)) return [];
  return raw
    .map((item) => {
      if (typeof item === "string") return { id: item, question: item };
      if (item && typeof item === "object") {
        const record = item as Record<string, unknown>;
        return {
          id: String(record.id || record.question || ""),
          question: String(record.question || record.content || ""),
        };
      }
      return { id: "", question: "" };
    })
    .filter((item) => item.id && item.question);
});

function timelineStageText(name: string) {
  return (
    {
      parse: "文档解析",
      chunk: "内容切分",
      embed: "向量生成",
      upsert: "索引入库",
      finalize: "完成收尾",
    }[name] || name
  );
}

function timelineStatusText(status: string) {
  return (
    {
      pending: "等待中",
      running: "处理中",
      done: "已完成",
      failed: "失败",
      cancelled: "已取消",
      skipped: "已跳过",
    }[status] || status
  );
}

function timelineStatusColor(status: string) {
  return (
    {
      pending: "gray",
      running: "blue",
      done: "green",
      failed: "red",
      cancelled: "gray",
      skipped: "gray",
    }[status] || "gray"
  );
}

function formatDuration(ms?: number | null) {
  if (ms === undefined || ms === null) return "-";
  if (ms < 1000) return `${Math.max(ms, 0)} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}

async function refresh() {
  await Promise.all([
    kbStore.loadKnowledgeBase(kbId.value),
    kbStore.loadTags(kbId.value),
    kbStore.loadDocuments(kbId.value, filters.value),
    kbStore.loadTasks({ knowledge_base_id: kbId.value }),
  ]);
}

async function resolveUploadTaskId(documentId: string) {
  await kbStore.loadTasks({ knowledge_base_id: kbId.value });
  return kbStore.tasks.find((task) => task.document_id === documentId)?.id;
}

async function uploadFiles(files: File[]) {
  const queueItems: UploadQueueItem[] = files.map((file, index) => ({
    id: `${Date.now()}-${index}-${file.name}`,
    fileName: file.name,
    fileSize: file.size,
    status: "pending",
  }));
  uploadQueue.value = [...uploadQueue.value, ...queueItems];
  uploadQueueRunning.value = true;
  try {
    for (let index = 0; index < files.length; index += 1) {
      const file = files[index];
      const queueItem = queueItems[index];
      try {
        queueItem.status = "uploading";
        const uploadedDocument = await kbStore.uploadDocument(kbId.value, file);
        queueItem.documentId = uploadedDocument.id;
        queueItem.status = "queued";
        queueItem.taskId = await resolveUploadTaskId(uploadedDocument.id);
        queueItem.status = "processing";
        await kbStore.pollDocument(uploadedDocument.id);
        queueItem.status = "completed";
        queueItem.noticeMessage = undefined;
      } catch (error) {
        if (error instanceof DocumentProcessingTimeoutError) {
          queueItem.status = "processing";
          queueItem.noticeMessage = "解析仍在后台进行，请稍后刷新状态。";
          await kbStore.loadDocuments(kbId.value, filters.value);
          continue;
        }
        const reason = formatApiError(error instanceof Error ? error.message : error);
        queueItem.status = "failed";
        queueItem.errorMessage = queueItem.documentId ? `解析失败：${reason}` : `上传失败：${reason}`;
      }
    }
    const summary = uploadQueueSummary.value;
    if (summary.partial) {
      Message.warning(`部分成功：${summary.completed} 个完成，${summary.failed} 个失败`);
    } else if (summary.failed > 0) {
      Message.error(`上传队列完成，失败 ${summary.failed} 个`);
    } else if (summary.completed > 0) {
      Message.success(`上传队列完成，解析完成 ${summary.completed} 个`);
    }
    await refresh();
  } finally {
    uploadQueueRunning.value = false;
  }
}

async function openChunks(document: DocumentRead) {
  activeDocument.value = document;
  kbStore.currentDocument = document;
  drawerVisible.value = true;
  try {
    await Promise.all([
      kbStore.loadDocumentPreview(document.id),
      kbStore.loadChunks(document.id),
      kbStore.loadDocumentSpans(document.id),
    ]);
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

async function refreshProcessingTimeline() {
  if (!activeDocument.value) return;
  timelineLoading.value = true;
  try {
    await kbStore.loadDocumentSpans(activeDocument.value.id);
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  } finally {
    timelineLoading.value = false;
  }
}

async function openProcessingTimeline(document: DocumentRead) {
  activeDocument.value = document;
  kbStore.currentDocument = document;
  timelineVisible.value = true;
  await refreshProcessingTimeline();
}

async function jumpToPreviewChunk(chunkId: string) {
  await nextTick();
  document.getElementById(`preview-chunk-${chunkId}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function fillChunkForm(chunk: ChunkRead) {
  chunkForm.value.content = chunk.content || "";
  chunkForm.value.search_text = chunk.search_text || "";
  chunkForm.value.metadataText = JSON.stringify(chunk.metadata || {}, null, 2);
  chunkForm.value.is_enabled = chunk.is_enabled;
  chunkForm.value.generatedQuestion = "";
}

async function openChunkDetail(chunkId: string) {
  try {
    const chunk = await kbStore.loadChunkById(chunkId);
    fillChunkForm(chunk);
    chunkDetailVisible.value = true;
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

function chunkMetadataPayload() {
  try {
    return JSON.parse(chunkForm.value.metadataText || "{}");
  } catch {
    throw new Error("metadata 必须是合法 JSON");
  }
}

async function submitChunkUpdate() {
  const chunk = kbStore.currentChunkDetail;
  if (!chunk) return;
  chunkDetailSaving.value = true;
  try {
    const result = await kbStore.updateChunk(chunk.knowledge_id, chunk.id, {
      content: chunkForm.value.content,
      search_text: chunkForm.value.search_text || null,
      metadata: chunkMetadataPayload(),
      is_enabled: chunkForm.value.is_enabled,
    });
    fillChunkForm(result.chunk);
    if (activeDocument.value) {
      await Promise.all([
        kbStore.loadDocumentPreview(activeDocument.value.id),
        kbStore.loadChunks(activeDocument.value.id),
      ]);
    }
    if (result.requires_reindex) {
      Message.warning("内容变化后需要重建 embedding");
    } else {
      Message.success("Chunk 已保存");
    }
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  } finally {
    chunkDetailSaving.value = false;
  }
}

async function addGeneratedQuestion() {
  const chunk = kbStore.currentChunkDetail;
  const question = chunkForm.value.generatedQuestion.trim();
  if (!chunk || !question) {
    Message.warning("请输入生成问题");
    return;
  }
  generatedQuestionSaving.value = true;
  try {
    const updated = await kbStore.addGeneratedQuestion(chunk.id, question);
    fillChunkForm(updated);
    Message.success("新增生成问题成功");
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  } finally {
    generatedQuestionSaving.value = false;
  }
}

async function deleteGeneratedQuestion(questionId: string) {
  const chunk = kbStore.currentChunkDetail;
  if (!chunk) return;
  try {
    const updated = await kbStore.deleteGeneratedQuestion(chunk.id, questionId);
    fillChunkForm(updated);
    Message.success("删除生成问题成功");
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

async function downloadDocument(document: DocumentRead) {
  try {
    const blob = await kbStore.downloadDocument(document.id);
    const url = URL.createObjectURL(blob);
    const link = window.document.createElement("a");
    link.href = url;
    link.download = document.file_name || document.title || "document";
    link.click();
    URL.revokeObjectURL(url);
    Message.success("已开始下载原文件");
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

async function cancelDocumentParse(document: DocumentRead) {
  try {
    await kbStore.cancelDocumentParse(document.id);
    Message.success("用户已取消解析");
    await refresh();
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

async function openMoveDocument(document: DocumentRead) {
  movingDocumentIds.value = [document.id];
  targetKnowledgeBaseId.value = "";
  await kbStore.loadKnowledgeBases();
  moveDocumentVisible.value = true;
}

async function submitMoveDocument() {
  if (!targetKnowledgeBaseId.value) {
    Message.error("请选择目标知识库");
    return;
  }
  try {
    const result = await kbStore.moveDocuments(movingDocumentIds.value, targetKnowledgeBaseId.value);
    moveDocumentVisible.value = false;
    Message.success(`提交移动成功：已移动 ${result.moved} 个文档`);
    await refresh();
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

function canCancelDocumentParse(document: DocumentRead) {
  return ["pending", "processing"].includes(document.parse_status);
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

async function retryTask(taskId: string) {
  try {
    await kbStore.retryTask(taskId);
    Message.success("失败任务已重新提交");
    await refresh();
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

async function retryFailedTasks() {
  const failedTasks = kbStore.tasks.filter((task) => task.status === "failed");
  for (const task of failedTasks) {
    await retryTask(task.id);
  }
}

function openImport(mode: "text" | "url") {
  importMode.value = mode;
  importForm.value = { title: "", content: "", format: "markdown", url: "", tag_id: filters.value.tag_id };
  importVisible.value = true;
}

function tagName(tagId?: string | null) {
  return kbStore.tags.find((tag) => tag.id === tagId)?.name || "未分类";
}

function tagColor(tagId?: string | null) {
  return kbStore.tags.find((tag) => tag.id === tagId)?.color || "gray";
}

async function createTag() {
  try {
    await kbStore.createTag(kbId.value, tagForm.value);
    tagForm.value = { name: "", color: "#2563eb", sort_order: 0 };
    tagModalVisible.value = false;
    Message.success("标签已创建");
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

async function deleteTag(tagId: string) {
  try {
    await kbStore.deleteTag(kbId.value, tagId);
    if (filters.value.tag_id === tagId) filters.value.tag_id = "";
    Message.success("标签已删除");
    await refresh();
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

async function batchSetTag() {
  try {
    const tagId = batchTagId.value || null;
    await kbStore.assignDocumentTags(
      kbId.value,
      Object.fromEntries(kbStore.selectedDocumentIds.map((id) => [id, tagId])),
    );
    batchTagVisible.value = false;
    batchTagId.value = "";
    Message.success("批量设置标签完成");
    await refresh();
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

async function submitImport() {
  try {
    const document = importMode.value === "url"
      ? await kbStore.importUrl(kbId.value, { url: importForm.value.url, tag_id: importForm.value.tag_id || null })
      : await kbStore.importText(kbId.value, {
        title: importForm.value.title,
        content: importForm.value.content,
        format: importForm.value.format,
        tag_id: importForm.value.tag_id || null,
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
      <div class="section-heading">
        <div>
          <h2>标签筛选</h2>
          <p>按知识库标签查看文档，标签统计来自后端引用计数。</p>
        </div>
        <a-button size="small" @click="tagModalVisible = true">新建标签</a-button>
      </div>
      <a-space wrap>
        <a-tag
          :color="filters.tag_id ? 'gray' : 'blue'"
          checkable
          :checked="!filters.tag_id"
          @click="filters.tag_id = ''; refresh()"
        >
          全部
        </a-tag>
        <a-tag
          v-for="tag in kbStore.tags"
          :key="tag.id"
          :color="tag.color || 'blue'"
          checkable
          :checked="filters.tag_id === tag.id"
          @click="filters.tag_id = tag.id; refresh()"
        >
          {{ tag.name }} · {{ tag.knowledge_count }}
          <a-popconfirm content="删除前请先移除该标签下的文档或 FAQ。" @ok.stop="deleteTag(tag.id)">
            <span class="tag-delete">×</span>
          </a-popconfirm>
        </a-tag>
      </a-space>
    </section>

    <section class="content-card">
      <DocumentUpload :uploading="uploadQueueRunning || kbStore.uploading" :polling="kbStore.polling" @upload="uploadFiles" />
    </section>

    <section v-if="uploadQueue.length" class="content-card upload-queue-panel" data-testid="upload-queue">
      <div class="section-heading">
        <div>
          <h2>上传队列</h2>
          <p>
            总计 {{ uploadQueueSummary.total }} 个文件，
            完成 {{ uploadQueueSummary.completed }}，
            失败 {{ uploadQueueSummary.failed }}，
            待处理 {{ uploadQueueSummary.running }}。
            <span v-if="uploadQueueSummary.partial">部分成功</span>
          </p>
        </div>
        <a-button size="small" :disabled="uploadQueueRunning" @click="uploadQueue = []">清空队列</a-button>
      </div>
      <div class="upload-queue-list">
        <article
          v-for="queueItem in uploadQueue"
          :key="queueItem.id"
          class="upload-queue-item"
          data-testid="upload-queue-item"
        >
          <header>
            <strong>{{ queueItem.fileName }}</strong>
            <a-tag :color="uploadQueueStatusColor(queueItem.status)">
              {{ uploadQueueStatusText(queueItem.status) }}
            </a-tag>
          </header>
          <div class="upload-queue-meta">
            <span>{{ Math.ceil(queueItem.fileSize / 1024) }} KB</span>
            <span>Document ID：{{ queueItem.documentId || "-" }}</span>
            <span>Task ID：{{ queueItem.taskId || "-" }}</span>
          </div>
          <p v-if="queueItem.noticeMessage" class="muted-text">{{ queueItem.noticeMessage }}</p>
          <p v-if="queueItem.errorMessage" class="inline-error">{{ queueItem.errorMessage }}</p>
        </article>
      </div>
    </section>

    <section v-if="kbStore.batchOperationResult || kbStore.tasks.length" class="content-card batch-progress-panel">
      <div class="section-heading">
        <div>
          <h2>批处理进度</h2>
          <p>批量上传、重处理和删除的成功数、失败数和失败原因保持可见。</p>
        </div>
        <a-button
          size="small"
          :disabled="!kbStore.tasks.some((task) => task.status === 'failed')"
          @click="retryFailedTasks"
        >
          重试失败任务
        </a-button>
      </div>
      <div v-if="kbStore.batchOperationResult" class="batch-summary-grid">
        <span>总计 {{ kbStore.batchOperationResult.requested }} 项</span>
        <span>成功 {{ kbStore.batchOperationResult.succeeded }} 项</span>
        <span>失败 {{ kbStore.batchOperationResult.failed }} 项</span>
      </div>
      <div v-if="kbStore.batchOperationResult?.failures.length" class="batch-failure-list">
        <strong>失败原因</strong>
        <div v-for="failure in kbStore.batchOperationResult.failures" :key="failure.document_id" class="batch-failure-row">
          <span>{{ failure.document_id }}</span>
          <span>{{ failure.reason }}</span>
        </div>
      </div>
      <div class="task-list">
        <article v-for="task in kbStore.tasks" :key="task.id" class="task-list-item">
          <header>
            <strong>{{ task.task_type }}</strong>
            <a-tag :color="statusColor(task.status)">{{ statusText(task.status) }}</a-tag>
          </header>
          <a-progress :percent="task.progress / 100" size="small" />
          <p v-if="task.batch_summary" class="muted-text">
            批次 {{ task.batch_summary.total }} 项：
            完成 {{ task.batch_summary.completed }}，
            处理中 {{ task.batch_summary.processing }}，
            失败 {{ task.batch_summary.failed }}
          </p>
          <p v-if="task.error_message" class="inline-error">{{ task.error_message }}</p>
          <a-button v-if="task.status === 'failed'" size="mini" @click="retryTask(task.id)">重试</a-button>
        </article>
      </div>
    </section>

    <section class="content-card">
      <div class="section-heading">
        <div>
          <h2>文档列表</h2>
          <p>筛选、批量处理、任务状态和失败原因保持可见。</p>
        </div>
        <a-space>
          <a-button :disabled="!kbStore.selectedDocumentIds.length" @click="batchTagVisible = true">批量设置标签</a-button>
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
        <a-form-item label="标签">
          <a-select v-model="filters.tag_id" allow-clear placeholder="标签筛选" @change="refresh">
            <a-option v-for="tag in kbStore.tags" :key="tag.id" :value="tag.id">{{ tag.name }}</a-option>
          </a-select>
        </a-form-item>
      </div>
      <a-table :data="kbStore.documents" :pagination="false" row-key="id">
        <template #columns>
          <a-table-column title="选择" :width="70">
            <template #cell="{ record }">
              <a-checkbox :model-value="checked(record.id)" @change="(value) => toggleSelected(record.id, Boolean(value))" />
            </template>
          </a-table-column>
          <a-table-column title="文档" data-index="title" />
          <a-table-column title="标签">
            <template #cell="{ record }">
              <a-tag :color="tagColor(record.tag_id)">{{ tagName(record.tag_id) }}</a-tag>
            </template>
          </a-table-column>
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
                <a-button size="mini" @click="openChunks(record)">文档预览</a-button>
                <a-button
                  v-if="['pending', 'processing', 'failed'].includes(record.parse_status)"
                  size="mini"
                  @click="openProcessingTimeline(record)"
                >
                  处理时间线
                </a-button>
                <a-button size="mini" @click="downloadDocument(record)">下载原文件</a-button>
                <a-popconfirm
                  v-if="canCancelDocumentParse(record)"
                  content="确认取消解析？当前已写入的部分结果会保留，可重新处理。"
                  type="warning"
                  @ok="cancelDocumentParse(record)"
                >
                  <a-button size="mini" status="warning">取消解析</a-button>
                </a-popconfirm>
                <a-button size="mini" @click="openMoveDocument(record)">移动到知识库</a-button>
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

    <a-drawer v-model:visible="drawerVisible" :width="860" :title="activeDocument?.title || '文档预览'">
      <div v-if="kbStore.currentDocumentPreview" class="preview-layout">
        <aside class="preview-outline" data-testid="preview-outline">
          <h3>文档预览</h3>
          <a-tag :color="statusColor(kbStore.currentDocumentPreview.status)">
            {{ statusText(kbStore.currentDocumentPreview.status) }}
          </a-tag>
          <p v-if="kbStore.currentDocumentPreview.summary">{{ kbStore.currentDocumentPreview.summary }}</p>
          <p v-if="kbStore.currentDocumentPreview.error_message" class="inline-error">
            {{ kbStore.currentDocumentPreview.error_message }}
          </p>
          <div class="processing-timeline" data-testid="processing-timeline">
            <header class="processing-timeline__header">
              <div>
                <h3>处理时间线</h3>
                <small>
                  Attempt {{ kbStore.currentProcessingTimeline?.attempt ?? "-" }}
                  · {{ timelineStatusText(kbStore.currentProcessingTimeline?.root.status || "pending") }}
                </small>
              </div>
              <a-button size="mini" :loading="timelineLoading" @click="refreshProcessingTimeline">手动刷新</a-button>
            </header>
            <!-- 无阶段记录时显示当前文档状态占位 -->
            <p v-if="kbStore.currentProcessingTimeline?.attempt === 0" class="muted-text">
              历史文档没有处理明细，已根据当前状态生成占位阶段。
            </p>
            <div v-if="kbStore.currentProcessingTimeline" class="timeline-stage-list">
              <article
                v-for="stage in kbStore.currentProcessingTimeline.stages"
                :key="stage.name"
                class="timeline-stage"
                :class="`timeline-stage--${stage.status}`"
              >
                <span class="timeline-stage__dot" />
                <div class="timeline-stage__body">
                  <header>
                    <strong>{{ timelineStageText(stage.name) }}</strong>
                    <a-tag :color="timelineStatusColor(stage.status)">
                      {{ timelineStatusText(stage.status) }}
                    </a-tag>
                  </header>
                  <small>{{ formatDuration(stage.duration_ms) }}</small>
                  <p v-if="stage.error_message" class="inline-error">{{ stage.error_message }}</p>
                </div>
              </article>
            </div>
          </div>
          <a-button
            v-for="chunk in kbStore.currentDocumentPreview.chunks"
            :key="chunk.id"
            size="mini"
            long
            @click="jumpToPreviewChunk(chunk.id)"
          >
            #{{ chunk.chunk_index }} {{ chunk.context_header || chunk.chunk_type }}
          </a-button>
        </aside>
        <section class="preview-content" data-testid="preview-content">
          <article
            v-for="chunk in kbStore.currentDocumentPreview.chunks"
            :id="`preview-chunk-${chunk.id}`"
            :key="chunk.id"
            class="chunk-item"
          >
            <header>
              <strong>#{{ chunk.chunk_index }}</strong>
              <a-tag color="green">{{ chunk.chunk_type }}</a-tag>
              <a-button size="mini" @click="openChunkDetail(chunk.id)">Chunk 详情</a-button>
            </header>
            <small v-if="chunk.context_header">{{ chunk.context_header }}</small>
            <p>{{ chunk.content_preview }}</p>
          </article>
          <pre v-if="!kbStore.currentDocumentPreview.chunks.length">{{ kbStore.currentDocumentPreview.content_preview }}</pre>
        </section>
      </div>
      <a-empty v-else description="暂无预览" />
    </a-drawer>

    <a-drawer
      v-model:visible="chunkDetailVisible"
      :width="680"
      :title="kbStore.currentChunkDetail ? `Chunk #${kbStore.currentChunkDetail.chunk_index}` : 'Chunk 详情'"
      data-testid="chunk-detail-drawer"
    >
      <div v-if="kbStore.currentChunkDetail" class="modal-form">
        <a-alert
          type="warning"
          content="内容变化后需要重建 embedding；保存会立即更新 chunk、关键词检索文本和启停状态。"
        />
        <div class="table-stack">
          <span>Chunk ID：{{ kbStore.currentChunkDetail.id }}</span>
          <span>Document ID：{{ kbStore.currentChunkDetail.knowledge_id }}</span>
        </div>
        <a-form-item label="启用 chunk">
          <a-switch v-model="chunkForm.is_enabled" />
        </a-form-item>
        <a-form-item label="内容">
          <a-textarea v-model="chunkForm.content" :auto-size="{ minRows: 6, maxRows: 12 }" />
        </a-form-item>
        <a-form-item label="search_text">
          <a-textarea v-model="chunkForm.search_text" :auto-size="{ minRows: 4, maxRows: 8 }" />
        </a-form-item>
        <a-form-item label="metadata">
          <a-textarea v-model="chunkForm.metadataText" :auto-size="{ minRows: 4, maxRows: 8 }" />
        </a-form-item>
        <a-button type="primary" :loading="chunkDetailSaving" @click="submitChunkUpdate">保存 chunk</a-button>

        <section class="chunk-question-panel">
          <div class="section-heading">
            <div>
              <h3>生成问题</h3>
              <p>这些问题会写入 chunk metadata，并进入关键词检索文本。</p>
            </div>
          </div>
          <div class="form-grid form-grid--compact">
            <a-form-item label="问题">
              <a-input v-model="chunkForm.generatedQuestion" placeholder="输入一个用户可能会问的问题" />
            </a-form-item>
            <a-button :loading="generatedQuestionSaving" @click="addGeneratedQuestion">新增生成问题</a-button>
          </div>
          <div class="task-list">
            <article v-for="question in currentChunkGeneratedQuestions" :key="question.id" class="task-list-item">
              <header>
                <strong>{{ question.question }}</strong>
                <a-popconfirm content="确认删除这个生成问题？" @ok="deleteGeneratedQuestion(question.id)">
                  <a-button size="mini" status="danger">删除生成问题</a-button>
                </a-popconfirm>
              </header>
              <small>{{ question.id }}</small>
            </article>
          </div>
          <a-empty v-if="!currentChunkGeneratedQuestions.length" description="暂无生成问题" />
        </section>
      </div>
      <a-empty v-else description="未选择 chunk" />
    </a-drawer>

    <a-drawer
      v-model:visible="timelineVisible"
      :width="520"
      :title="activeDocument ? `${activeDocument.title} · 处理时间线` : '处理时间线'"
    >
      <div class="processing-timeline processing-timeline--drawer" data-testid="processing-timeline-drawer">
        <header class="processing-timeline__header">
          <div>
            <h3>处理时间线</h3>
            <small>
              Attempt {{ kbStore.currentProcessingTimeline?.attempt ?? "-" }}
              · {{ timelineStatusText(kbStore.currentProcessingTimeline?.root.status || activeDocument?.parse_status || "pending") }}
            </small>
          </div>
          <a-button size="mini" :loading="timelineLoading" @click="refreshProcessingTimeline">手动刷新</a-button>
        </header>
        <a-spin v-if="timelineLoading && !kbStore.currentProcessingTimeline" />
        <template v-else-if="kbStore.currentProcessingTimeline">
          <p v-if="kbStore.currentProcessingTimeline.attempt === 0" class="muted-text">
            历史文档没有处理明细，已根据当前状态生成占位阶段。
          </p>
          <article
            v-if="kbStore.currentProcessingTimeline.root.error_message"
            class="timeline-root-error"
          >
            {{ kbStore.currentProcessingTimeline.root.error_message }}
          </article>
          <div class="timeline-stage-list">
            <article
              v-for="stage in kbStore.currentProcessingTimeline.stages"
              :key="stage.name"
              class="timeline-stage"
              :class="`timeline-stage--${stage.status}`"
            >
              <span class="timeline-stage__dot" />
              <div class="timeline-stage__body">
                <header>
                  <strong>{{ timelineStageText(stage.name) }}</strong>
                  <a-tag :color="timelineStatusColor(stage.status)">
                    {{ timelineStatusText(stage.status) }}
                  </a-tag>
                </header>
                <small>{{ formatDuration(stage.duration_ms) }}</small>
                <p v-if="stage.error_message" class="inline-error">{{ stage.error_message }}</p>
              </div>
            </article>
          </div>
        </template>
        <a-empty v-else description="暂无处理时间线" />
      </div>
    </a-drawer>

    <a-modal v-model:visible="importVisible" :title="importMode === 'url' ? 'URL 导入' : '在线文本导入'" @ok="submitImport">
      <div v-if="importMode === 'url'" class="modal-form">
        <a-alert type="info" content="URL 导入仅抓取 HTML title 和可读正文，本地与内网地址会被拒绝。" />
        <a-form-item label="URL"><a-input v-model="importForm.url" placeholder="https://example.com/article" /></a-form-item>
        <a-form-item label="标签">
          <a-select v-model="importForm.tag_id" allow-clear placeholder="可选标签">
            <a-option v-for="tag in kbStore.tags" :key="tag.id" :value="tag.id">{{ tag.name }}</a-option>
          </a-select>
        </a-form-item>
      </div>
      <div v-else class="modal-form">
        <a-form-item label="标题"><a-input v-model="importForm.title" /></a-form-item>
        <a-form-item label="标签">
          <a-select v-model="importForm.tag_id" allow-clear placeholder="可选标签">
            <a-option v-for="tag in kbStore.tags" :key="tag.id" :value="tag.id">{{ tag.name }}</a-option>
          </a-select>
        </a-form-item>
        <a-form-item label="格式">
          <a-radio-group v-model="importForm.format" type="button">
            <a-radio value="markdown">Markdown</a-radio>
            <a-radio value="text">纯文本</a-radio>
          </a-radio-group>
        </a-form-item>
        <a-form-item label="内容"><a-textarea v-model="importForm.content" :auto-size="{ minRows: 8, maxRows: 14 }" /></a-form-item>
      </div>
    </a-modal>

    <a-modal v-model:visible="tagModalVisible" title="新建标签" @ok="createTag">
      <div class="modal-form">
        <a-form-item label="名称"><a-input v-model="tagForm.name" placeholder="例如：产品资料" /></a-form-item>
        <a-form-item label="颜色"><a-input v-model="tagForm.color" placeholder="#2563eb" /></a-form-item>
      </div>
    </a-modal>

    <a-modal v-model:visible="batchTagVisible" title="批量设置标签" @ok="batchSetTag">
      <div class="modal-form">
        <a-form-item label="标签">
          <a-select v-model="batchTagId" allow-clear placeholder="选择标签，清空则设为未分类">
            <a-option v-for="tag in kbStore.tags" :key="tag.id" :value="tag.id">{{ tag.name }}</a-option>
          </a-select>
        </a-form-item>
        <p class="muted-text">将为 {{ kbStore.selectedDocumentIds.length }} 个文档设置标签；清空选择会移除标签并设为未分类。</p>
      </div>
    </a-modal>

    <a-modal v-model:visible="moveDocumentVisible" title="移动到知识库" @ok="submitMoveDocument">
      <div class="modal-form">
        <a-alert
          type="info"
          content="仅展示同类型且使用相同 Embedding 模型的知识库；移动后来源知识库不再包含该文档。"
        />
        <a-form-item label="目标知识库">
          <a-select v-model="targetKnowledgeBaseId" placeholder="选择目标知识库">
            <a-option v-for="kb in moveTargetKnowledgeBases" :key="kb.id" :value="kb.id">
              {{ kb.name }}
            </a-option>
          </a-select>
        </a-form-item>
        <p class="muted-text">提交移动 {{ movingDocumentIds.length }} 个文档。</p>
      </div>
    </a-modal>
  </main>
</template>
