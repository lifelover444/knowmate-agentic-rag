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
const activeDocument = ref<DocumentRead | null>(null);
const kbId = computed(() => String(route.params.kbId || ""));

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
  await Promise.all([kbStore.loadKnowledgeBase(kbId.value), kbStore.loadDocuments(kbId.value)]);
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
        <a-popconfirm content="确认重建整个知识库？" type="warning" @ok="reprocessKb">
          <a-button data-testid="reprocess-kb" :loading="kbStore.reprocessing">重建知识库</a-button>
        </a-popconfirm>
      </template>
    </a-page-header>

    <section class="content-card">
      <DocumentUpload :uploading="kbStore.uploading" :polling="kbStore.polling" @upload="upload" />
    </section>

    <section class="content-card">
      <a-table :data="kbStore.documents" :pagination="false" row-key="id">
        <template #columns>
          <a-table-column title="文档" data-index="title" />
          <a-table-column title="文件名" data-index="file_name" />
          <a-table-column title="状态">
            <template #cell="{ record }">
              <a-tag :color="statusColor(record.parse_status)">{{ statusText(record.parse_status) }}</a-tag>
              <p v-if="record.error_message" class="inline-error">{{ record.error_message }}</p>
            </template>
          </a-table-column>
          <a-table-column title="大小">
            <template #cell="{ record }">{{ record.file_size }} bytes</template>
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
          <p>{{ chunk.content }}</p>
        </article>
      </div>
      <a-empty v-else description="暂无切片" />
    </a-drawer>
  </main>
</template>
