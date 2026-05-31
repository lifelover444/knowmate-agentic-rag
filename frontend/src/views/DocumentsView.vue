<script setup lang="ts">
import { Message } from "@arco-design/web-vue";
import { computed, nextTick, onMounted, ref } from "vue";
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
const filters = ref({ status: "", file_type: "", keyword: "", tag_id: "" });
const importForm = ref({ title: "", content: "", format: "markdown", url: "", tag_id: "" });
const tagModalVisible = ref(false);
const tagForm = ref({ name: "", color: "#2563eb", sort_order: 0 });
const batchTagVisible = ref(false);
const batchTagId = ref<string>("");

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
      queued: "等待处理",
      pending: "等待解析",
      processing: "解析中",
      completed: "解析完成",
      failed: "解析失败",
    }[status] || status
  );
}

async function refresh() {
  await Promise.all([
    kbStore.loadKnowledgeBase(kbId.value),
    kbStore.loadTags(kbId.value),
    kbStore.loadDocuments(kbId.value, filters.value),
    kbStore.loadTasks({ knowledge_base_id: kbId.value }),
  ]);
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
    await Promise.all([kbStore.loadDocumentPreview(document.id), kbStore.loadChunks(document.id)]);
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

async function jumpToPreviewChunk(chunkId: string) {
  await nextTick();
  document.getElementById(`preview-chunk-${chunkId}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
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
      <DocumentUpload :uploading="kbStore.uploading" :polling="kbStore.polling" @upload="upload" />
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
            </header>
            <small v-if="chunk.context_header">{{ chunk.context_header }}</small>
            <p>{{ chunk.content_preview }}</p>
          </article>
          <pre v-if="!kbStore.currentDocumentPreview.chunks.length">{{ kbStore.currentDocumentPreview.content_preview }}</pre>
        </section>
      </div>
      <a-empty v-else description="暂无预览" />
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
  </main>
</template>
