import { ref } from "vue";
import { defineStore } from "pinia";
import { deleteRequest, getJson, postForm, postJson } from "../utils/api";
import type { ChunkRead, DocumentRead, KnowledgeBasePayload, KnowledgeBaseRead } from "../types/api";

export const documentProcessingMaxPolls = 300;

export const useKnowledgeBaseStore = defineStore("knowledgeBase", () => {
  const knowledgeBases = ref<KnowledgeBaseRead[]>([]);
  const currentKb = ref<KnowledgeBaseRead | null>(null);
  const documents = ref<DocumentRead[]>([]);
  const chunks = ref<ChunkRead[]>([]);
  const currentDocument = ref<DocumentRead | null>(null);
  const uploading = ref(false);
  const polling = ref(false);
  const loading = ref(false);
  const reprocessing = ref(false);

  async function loadKnowledgeBases() {
    loading.value = true;
    try {
      knowledgeBases.value = await getJson<KnowledgeBaseRead[]>("/knowledge-bases");
      return knowledgeBases.value;
    } finally {
      loading.value = false;
    }
  }

  async function loadKnowledgeBase(kbId: string) {
    currentKb.value = await getJson<KnowledgeBaseRead>(`/knowledge-bases/${kbId}`);
    return currentKb.value;
  }

  async function createKnowledgeBase(payload: KnowledgeBasePayload) {
    const created = await postJson<KnowledgeBaseRead, KnowledgeBasePayload>("/knowledge-bases", payload);
    currentKb.value = created;
    await loadKnowledgeBases();
    return created;
  }

  async function deleteKnowledgeBase(kbId: string) {
    await deleteRequest(`/knowledge-bases/${kbId}`);
    if (currentKb.value?.id === kbId) currentKb.value = null;
    await loadKnowledgeBases();
  }

  async function loadDocuments(kbId: string) {
    documents.value = await getJson<DocumentRead[]>(`/knowledge-bases/${kbId}/documents`);
    return documents.value;
  }

  async function uploadDocument(kbId: string, file: File) {
    uploading.value = true;
    try {
      const form = new FormData();
      form.append("file", file);
      const document = await postForm<DocumentRead>(`/knowledge-bases/${kbId}/documents/file`, form);
      currentDocument.value = document;
      await loadDocuments(kbId);
      return document;
    } finally {
      uploading.value = false;
    }
  }

  async function loadDocument(documentId: string) {
    currentDocument.value = await getJson<DocumentRead>(`/documents/${documentId}`);
    return currentDocument.value;
  }

  async function pollDocument(documentId: string) {
    polling.value = true;
    try {
      for (let index = 0; index < documentProcessingMaxPolls; index += 1) {
        const document = await loadDocument(documentId);
        if (document.parse_status === "completed") {
          await loadChunks(document.id);
          await loadDocuments(document.knowledge_base_id);
          return document;
        }
        if (document.parse_status === "failed") {
          throw new Error(document.error_message || "文档解析失败，请检查文件内容或模型配置。");
        }
        await new Promise((resolve) => setTimeout(resolve, 1000));
      }
      throw new Error("文档解析超时，请稍后刷新查看状态。");
    } finally {
      polling.value = false;
    }
  }

  async function loadChunks(documentId: string) {
    chunks.value = await getJson<ChunkRead[]>(`/documents/${documentId}/chunks`);
    return chunks.value;
  }

  async function deleteDocument(documentId: string) {
    const kbId = currentDocument.value?.knowledge_base_id || currentKb.value?.id;
    await deleteRequest(`/documents/${documentId}`);
    if (currentDocument.value?.id === documentId) {
      currentDocument.value = null;
      chunks.value = [];
    }
    if (kbId) await loadDocuments(kbId);
  }

  async function reprocessDocument(documentId: string) {
    reprocessing.value = true;
    try {
      const document = await postJson<DocumentRead>(`/documents/${documentId}/reprocess`);
      currentDocument.value = document;
      return document;
    } finally {
      reprocessing.value = false;
    }
  }

  async function reprocessKnowledgeBase(kbId: string) {
    reprocessing.value = true;
    try {
      await postJson(`/knowledge-bases/${kbId}/reprocess`);
      await loadKnowledgeBase(kbId);
      await loadDocuments(kbId);
    } finally {
      reprocessing.value = false;
    }
  }

  return {
    knowledgeBases,
    currentKb,
    documents,
    chunks,
    currentDocument,
    uploading,
    polling,
    loading,
    reprocessing,
    loadKnowledgeBases,
    loadKnowledgeBase,
    createKnowledgeBase,
    deleteKnowledgeBase,
    loadDocuments,
    uploadDocument,
    pollDocument,
    loadChunks,
    deleteDocument,
    reprocessDocument,
    reprocessKnowledgeBase,
  };
});
