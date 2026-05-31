import { ref } from "vue";
import { defineStore } from "pinia";
import { deleteRequest, downloadRequest, getJson, postForm, postJson, putJson } from "../utils/api";
import type {
  BatchDocumentResponse,
  ChunkRead,
  DocumentPreviewRead,
  DocumentRead,
  FAQExportFormat,
  FAQEntryRead,
  FAQImportResult,
  FAQSearchTestResult,
  KnowledgeBasePayload,
  KnowledgeBaseRead,
  KnowledgeTagPayload,
  KnowledgeTagRead,
  ProcessingTaskRead,
} from "../types/api";

export const documentProcessingMaxPolls = 300;

export const useKnowledgeBaseStore = defineStore("knowledgeBase", () => {
  const knowledgeBases = ref<KnowledgeBaseRead[]>([]);
  const currentKb = ref<KnowledgeBaseRead | null>(null);
  const documents = ref<DocumentRead[]>([]);
  const chunks = ref<ChunkRead[]>([]);
  const currentDocument = ref<DocumentRead | null>(null);
  const currentDocumentPreview = ref<DocumentPreviewRead | null>(null);
  const selectedDocumentIds = ref<string[]>([]);
  const faqs = ref<FAQEntryRead[]>([]);
  const batchOperationResult = ref<BatchDocumentResponse | null>(null);
  const latestFaqImportResult = ref<FAQImportResult | null>(null);
  const faqSearchHits = ref<FAQSearchTestResult[]>([]);
  const tags = ref<KnowledgeTagRead[]>([]);
  const tasks = ref<ProcessingTaskRead[]>([]);
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

  async function updateKnowledgeBase(kbId: string, payload: Partial<KnowledgeBasePayload>) {
    const updated = await putJson<KnowledgeBaseRead, Partial<KnowledgeBasePayload>>(`/knowledge-bases/${kbId}`, payload);
    currentKb.value = updated;
    await loadKnowledgeBases();
    return updated;
  }

  async function deleteKnowledgeBase(kbId: string) {
    await deleteRequest(`/knowledge-bases/${kbId}`);
    if (currentKb.value?.id === kbId) currentKb.value = null;
    await loadKnowledgeBases();
  }

  async function loadDocuments(kbId: string, filters: Record<string, string> = {}) {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value) params.set(key, value);
    });
    const suffix = params.toString() ? `?${params.toString()}` : "";
    documents.value = await getJson<DocumentRead[]>(`/knowledge-bases/${kbId}/documents${suffix}`);
    return documents.value;
  }

  async function loadTags(kbId: string, keyword = "") {
    const params = new URLSearchParams();
    if (keyword) params.set("keyword", keyword);
    const suffix = params.toString() ? `?${params.toString()}` : "";
    tags.value = await getJson<KnowledgeTagRead[]>(`/knowledge-bases/${kbId}/tags${suffix}`);
    return tags.value;
  }

  async function createTag(kbId: string, payload: KnowledgeTagPayload) {
    const tag = await postJson<KnowledgeTagRead, KnowledgeTagPayload>(`/knowledge-bases/${kbId}/tags`, payload);
    await loadTags(kbId);
    return tag;
  }

  async function updateTag(kbId: string, tagId: string, payload: Partial<KnowledgeTagPayload>) {
    const tag = await putJson<KnowledgeTagRead, Partial<KnowledgeTagPayload>>(`/knowledge-bases/${kbId}/tags/${tagId}`, payload);
    await loadTags(kbId);
    return tag;
  }

  async function deleteTag(kbId: string, tagId: string) {
    await deleteRequest(`/knowledge-bases/${kbId}/tags/${tagId}`);
    await loadTags(kbId);
  }

  async function assignDocumentTags(kbId: string, updates: Record<string, string | null>) {
    const result = await putJson<{ updated: number }, { updates: Record<string, string | null> }>(`/knowledge-bases/${kbId}/documents/tags`, { updates });
    await Promise.all([loadDocuments(kbId), loadTags(kbId)]);
    selectedDocumentIds.value = [];
    return result;
  }

  async function assignFaqTags(kbId: string, updates: Record<string, string | null>) {
    const result = await putJson<{ updated: number }, { updates: Record<string, string | null> }>(`/knowledge-bases/${kbId}/faqs/tags`, { updates });
    await Promise.all([loadFaqs(kbId), loadTags(kbId)]);
    return result;
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

  async function loadDocumentPreview(documentId: string) {
    currentDocumentPreview.value = await getJson<DocumentPreviewRead>(`/documents/${documentId}/preview`);
    return currentDocumentPreview.value;
  }

  async function deleteDocument(documentId: string) {
    const kbId = currentDocument.value?.knowledge_base_id || currentKb.value?.id;
    await deleteRequest(`/documents/${documentId}`);
    if (currentDocument.value?.id === documentId) {
      currentDocument.value = null;
      currentDocumentPreview.value = null;
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

  async function batchDeleteDocuments(kbId: string, documentIds: string[]) {
    batchOperationResult.value = await postJson<BatchDocumentResponse>(`/knowledge-bases/${kbId}/documents/batch-delete`, { document_ids: documentIds });
    await loadDocuments(kbId);
    selectedDocumentIds.value = [];
    return batchOperationResult.value;
  }

  async function batchReprocessDocuments(kbId: string, documentIds: string[]) {
    batchOperationResult.value = await postJson<BatchDocumentResponse>(`/knowledge-bases/${kbId}/documents/batch-reprocess`, { document_ids: documentIds });
    await Promise.all([loadDocuments(kbId), loadTasks({ knowledge_base_id: kbId })]);
    selectedDocumentIds.value = [];
    return batchOperationResult.value;
  }

  async function importText(kbId: string, payload: { title: string; content: string; format: string; tag_id?: string | null }) {
    const document = await postJson<DocumentRead>(`/knowledge-bases/${kbId}/documents/text`, payload);
    await loadDocuments(kbId);
    return document;
  }

  async function importUrl(kbId: string, payload: { url: string; tag_id?: string | null }) {
    const document = await postJson<DocumentRead>(`/knowledge-bases/${kbId}/documents/url`, payload);
    await loadDocuments(kbId);
    return document;
  }

  async function loadTasks(filters: Record<string, string> = {}) {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value) params.set(key, value);
    });
    const suffix = params.toString() ? `?${params.toString()}` : "";
    tasks.value = await getJson<ProcessingTaskRead[]>(`/tasks${suffix}`);
    return tasks.value;
  }

  async function retryTask(taskId: string) {
    const task = await postJson<ProcessingTaskRead>(`/tasks/${taskId}/retry`);
    await loadTasks();
    return task;
  }

  async function loadFaqs(kbId: string, filters: Record<string, string> = {}) {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value) params.set(key, value);
    });
    const suffix = params.toString() ? `?${params.toString()}` : "";
    faqs.value = await getJson<FAQEntryRead[]>(`/knowledge-bases/${kbId}/faqs${suffix}`);
    return faqs.value;
  }

  async function createFaq(kbId: string, payload: { question: string; answer: string; metadata?: Record<string, unknown>; enabled: boolean }) {
    const faq = await postJson<FAQEntryRead>(`/knowledge-bases/${kbId}/faqs`, payload);
    await loadFaqs(kbId);
    return faq;
  }

  async function updateFaq(kbId: string, faqId: string, payload: Partial<{ question: string; answer: string; metadata: Record<string, unknown>; enabled: boolean }>) {
    const faq = await putJson<FAQEntryRead>(`/knowledge-bases/${kbId}/faqs/${faqId}`, payload);
    await loadFaqs(kbId);
    return faq;
  }

  async function deleteFaq(kbId: string, faqId: string) {
    await deleteRequest(`/knowledge-bases/${kbId}/faqs/${faqId}`);
    await loadFaqs(kbId);
  }

  async function rebuildFaq(kbId: string, faqId: string) {
    const faq = await postJson<FAQEntryRead>(`/knowledge-bases/${kbId}/faqs/${faqId}/rebuild-index`);
    await loadFaqs(kbId);
    return faq;
  }

  async function importFaqs(kbId: string, file: File, mode: "append" | "replace") {
    const form = new FormData();
    form.append("file", file);
    form.append("mode", mode);
    const result = await postForm<{ imported: number; failed: number; errors?: Array<{ row: number; error: string }> }>(`/knowledge-bases/${kbId}/faqs/import`, form);
    latestFaqImportResult.value = {
      total: Number(result.imported || 0) + Number(result.failed || 0),
      imported: Number(result.imported || 0),
      failed: Number(result.failed || 0),
      mode,
      failures: (result.errors || []).map((error) => ({
        row: error.row,
        question: null,
        error: error.error,
      })),
    };
    await Promise.all([loadFaqs(kbId), loadTags(kbId)]);
    return latestFaqImportResult.value;
  }

  async function exportFaqs(kbId: string, format: FAQExportFormat) {
    return downloadRequest(`/knowledge-bases/${kbId}/faqs/export?format=${format}`);
  }

  async function searchFaqKnowledge(kbId: string, query: string, topK: number, enableRerank: boolean) {
    const response = await postJson<{ hits: FAQSearchTestResult[] }>("/knowledge-search", {
      knowledge_base_id: kbId,
      query,
      mode: "hybrid",
      top_k: topK,
      enable_rerank: enableRerank,
    });
    faqSearchHits.value = response.hits;
    return response.hits;
  }

  return {
    knowledgeBases,
    currentKb,
    documents,
    chunks,
    currentDocument,
    currentDocumentPreview,
    selectedDocumentIds,
    faqs,
    batchOperationResult,
    latestFaqImportResult,
    faqSearchHits,
    tags,
    tasks,
    uploading,
    polling,
    loading,
    reprocessing,
    loadKnowledgeBases,
    loadKnowledgeBase,
    createKnowledgeBase,
    updateKnowledgeBase,
    deleteKnowledgeBase,
    loadTags,
    createTag,
    updateTag,
    deleteTag,
    assignDocumentTags,
    assignFaqTags,
    loadDocuments,
    uploadDocument,
    pollDocument,
    loadChunks,
    loadDocumentPreview,
    deleteDocument,
    reprocessDocument,
    reprocessKnowledgeBase,
    batchDeleteDocuments,
    batchReprocessDocuments,
    importText,
    importUrl,
    loadTasks,
    retryTask,
    loadFaqs,
    createFaq,
    updateFaq,
    deleteFaq,
    rebuildFaq,
    importFaqs,
    exportFaqs,
    searchFaqKnowledge,
  };
});
