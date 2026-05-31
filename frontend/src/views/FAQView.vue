<script setup lang="ts">
import { Message } from "@arco-design/web-vue";
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useKnowledgeBaseStore } from "../stores/knowledgeBase";
import { formatApiError } from "../utils/api";
import type { FAQEntryRead } from "../types/api";

const route = useRoute();
const router = useRouter();
const kbStore = useKnowledgeBaseStore();
const kbId = computed(() => String(route.params.kbId || ""));
const editing = ref<FAQEntryRead | null>(null);
const modalVisible = ref(false);
const saving = ref(false);
const importVisible = ref(false);
const importing = ref(false);
const exportLoading = ref<"csv" | "xlsx" | "">("");
const searchVisible = ref(false);
const searching = ref(false);
const importMode = ref<"append" | "replace">("append");
const selectedImportFile = ref<File | null>(null);
const filters = ref({ tag_id: "" });
const form = reactive({
  question: "",
  answer: "",
  metadataText: "{}",
  tag_id: "",
  enabled: true,
});
const searchForm = reactive({
  query: "",
  topK: 5,
  enableRerank: false,
});

function openCreate() {
  editing.value = null;
  form.question = "";
  form.answer = "";
  form.metadataText = "{}";
  form.tag_id = filters.value.tag_id;
  form.enabled = true;
  modalVisible.value = true;
}

function openEdit(record: FAQEntryRead) {
  editing.value = record;
  form.question = record.question;
  form.answer = record.answer;
  form.metadataText = JSON.stringify(record.metadata || {}, null, 2);
  form.tag_id = record.tag_id || "";
  form.enabled = record.enabled;
  modalVisible.value = true;
}

function metadataPayload() {
  try {
    return JSON.parse(form.metadataText || "{}");
  } catch {
    throw new Error("metadata 必须是合法 JSON");
  }
}

async function submit() {
  saving.value = true;
  try {
    const payload = {
      question: form.question,
      answer: form.answer,
      metadata: metadataPayload(),
      tag_id: form.tag_id || null,
      enabled: form.enabled,
    };
    if (editing.value) {
      await kbStore.updateFaq(kbId.value, editing.value.id, payload);
    } else {
      await kbStore.createFaq(kbId.value, payload);
    }
    modalVisible.value = false;
    Message.success("FAQ 条目已保存并更新索引");
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  } finally {
    saving.value = false;
  }
}

async function toggle(record: FAQEntryRead) {
  try {
    await kbStore.updateFaq(kbId.value, record.id, { enabled: !record.enabled });
    Message.success(record.enabled ? "FAQ 已停用" : "FAQ 已启用");
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

async function rebuild(record: FAQEntryRead) {
  try {
    await kbStore.rebuildFaq(kbId.value, record.id);
    Message.success("FAQ 索引已重建");
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

async function remove(record: FAQEntryRead) {
  try {
    await kbStore.deleteFaq(kbId.value, record.id);
    Message.success("FAQ 条目已删除");
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

function tagName(tagId?: string | null) {
  return kbStore.tags.find((tag) => tag.id === tagId)?.name || "未分类";
}

function tagColor(tagId?: string | null) {
  return kbStore.tags.find((tag) => tag.id === tagId)?.color || "gray";
}

async function refreshFaqs() {
  await Promise.all([
    kbStore.loadKnowledgeBase(kbId.value),
    kbStore.loadTags(kbId.value),
    kbStore.loadFaqs(kbId.value, filters.value),
  ]);
}

async function assignFaqTag(record: FAQEntryRead, tagId: string) {
  try {
    await kbStore.assignFaqTags(kbId.value, { [record.id]: tagId || null });
    Message.success("FAQ 标签已更新");
    await refreshFaqs();
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

function onImportFileChange(_: unknown, currentFile?: { file?: File; originFile?: File }) {
  selectedImportFile.value = currentFile?.file || currentFile?.originFile || null;
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

async function submitImport() {
  if (!selectedImportFile.value) {
    Message.warning("请选择 CSV 或 XLSX 文件");
    return;
  }
  importing.value = true;
  try {
    await kbStore.importFaqs(kbId.value, selectedImportFile.value, importMode.value);
    importVisible.value = false;
    selectedImportFile.value = null;
    Message.success("FAQ 导入完成");
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  } finally {
    importing.value = false;
  }
}

async function exportFaqs(format: "csv" | "xlsx") {
  exportLoading.value = format;
  try {
    const blob = await kbStore.exportFaqs(kbId.value, format);
    downloadBlob(blob, `faqs.${format}`);
    Message.success(`FAQ 已导出 ${format.toUpperCase()}`);
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  } finally {
    exportLoading.value = "";
  }
}

async function runFaqSearch() {
  if (!searchForm.query.trim()) {
    Message.warning("请输入检索问题");
    return;
  }
  searching.value = true;
  try {
    await kbStore.searchFaqKnowledge(kbId.value, searchForm.query.trim(), searchForm.topK, searchForm.enableRerank);
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  } finally {
    searching.value = false;
  }
}

onMounted(() => {
  refreshFaqs().catch((error) => {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  });
});
</script>

<template>
  <main class="page-shell">
    <a-page-header
      :title="`${kbStore.currentKb?.name || 'FAQ'} · FAQ 管理`"
      subtitle="FAQ 条目会复用 chunks、Qdrant 和 quick-answer 检索管线。"
      @back="router.push('/knowledge-bases')"
    >
      <template #extra>
        <a-space>
          <a-button @click="router.push(`/knowledge-bases/${kbId}/documents`)">文档</a-button>
          <a-button @click="importVisible = true">FAQ 导入</a-button>
          <a-button :loading="exportLoading === 'csv'" @click="exportFaqs('csv')">导出 CSV</a-button>
          <a-button :loading="exportLoading === 'xlsx'" @click="exportFaqs('xlsx')">导出 XLSX</a-button>
          <a-button @click="searchVisible = true">FAQ 检索测试</a-button>
          <a-button type="primary" @click="openCreate">新增 FAQ</a-button>
        </a-space>
      </template>
    </a-page-header>

    <section v-if="kbStore.latestFaqImportResult" class="content-card faq-import-summary">
      <div class="section-heading">
        <div>
          <h2>导入结果</h2>
          <p>
            共 {{ kbStore.latestFaqImportResult.total }} 行，
            成功 {{ kbStore.latestFaqImportResult.imported }} 行，
            失败 {{ kbStore.latestFaqImportResult.failed }} 行。
          </p>
        </div>
        <a-tag :color="kbStore.latestFaqImportResult.mode === 'append' ? 'green' : 'orange'">
          {{ kbStore.latestFaqImportResult.mode === "append" ? "追加" : "替换" }}
        </a-tag>
      </div>
      <div v-if="kbStore.latestFaqImportResult.failures.length" class="faq-import-failures">
        <div v-for="failure in kbStore.latestFaqImportResult.failures" :key="failure.row" class="faq-import-failure">
          <strong>失败行 {{ failure.row }}</strong>
          <span>{{ failure.question || "空问题" }}</span>
          <span>{{ failure.error }}</span>
        </div>
      </div>
    </section>

    <section class="content-card">
      <div class="section-heading">
        <div>
          <h2>FAQ 标签</h2>
          <p>按标签筛选 FAQ 条目，并可在列表中直接调整分类。</p>
        </div>
        <a-select v-model="filters.tag_id" allow-clear placeholder="标签筛选" class="compact-select" @change="refreshFaqs">
          <a-option v-for="tag in kbStore.tags" :key="tag.id" :value="tag.id">{{ tag.name }}</a-option>
        </a-select>
      </div>
      <a-table :data="kbStore.faqs" :pagination="false" row-key="id">
        <template #columns>
          <a-table-column title="问题" data-index="question" />
          <a-table-column title="答案" data-index="answer" />
          <a-table-column title="标签">
            <template #cell="{ record }">
              <a-select
                :model-value="record.tag_id || ''"
                allow-clear
                size="small"
                placeholder="未分类"
                @change="(value) => assignFaqTag(record, String(value || ''))"
              >
                <a-option value="">未分类</a-option>
                <a-option v-for="tag in kbStore.tags" :key="tag.id" :value="tag.id">
                  {{ tag.name }}
                </a-option>
              </a-select>
              <a-tag :color="tagColor(record.tag_id)">{{ tagName(record.tag_id) }}</a-tag>
            </template>
          </a-table-column>
          <a-table-column title="状态">
            <template #cell="{ record }">
              <a-tag :color="record.enabled ? 'green' : 'gray'">{{ record.enabled ? "启用" : "停用" }}</a-tag>
            </template>
          </a-table-column>
          <a-table-column title="操作">
            <template #cell="{ record }">
              <a-space>
                <a-button size="mini" @click="openEdit(record)">编辑</a-button>
                <a-button size="mini" @click="toggle(record)">{{ record.enabled ? "停用" : "启用" }}</a-button>
                <a-button size="mini" @click="rebuild(record)">重建索引</a-button>
                <a-popconfirm content="确认删除这个 FAQ？" @ok="remove(record)">
                  <a-button size="mini" status="danger">删除</a-button>
                </a-popconfirm>
              </a-space>
            </template>
          </a-table-column>
        </template>
      </a-table>
      <a-empty v-if="!kbStore.faqs.length" description="暂无 FAQ 条目" />
    </section>

    <a-modal v-model:visible="modalVisible" title="FAQ 条目" :confirm-loading="saving" @ok="submit">
      <div class="modal-form">
        <a-form-item label="问题"><a-input v-model="form.question" /></a-form-item>
        <a-form-item label="答案"><a-textarea v-model="form.answer" :auto-size="{ minRows: 4, maxRows: 8 }" /></a-form-item>
        <a-form-item label="标签">
          <a-select v-model="form.tag_id" allow-clear placeholder="未分类">
            <a-option value="">未分类</a-option>
            <a-option v-for="tag in kbStore.tags" :key="tag.id" :value="tag.id">{{ tag.name }}</a-option>
          </a-select>
        </a-form-item>
        <a-form-item label="metadata"><a-textarea v-model="form.metadataText" :auto-size="{ minRows: 3, maxRows: 6 }" /></a-form-item>
        <a-form-item label="启用"><a-switch v-model="form.enabled" /></a-form-item>
      </div>
    </a-modal>

    <a-modal v-model:visible="importVisible" title="FAQ 导入" :confirm-loading="importing" @ok="submitImport">
      <div class="modal-form">
        <a-form-item label="导入模式">
          <a-radio-group v-model="importMode" type="button">
            <a-radio value="append">append</a-radio>
            <a-radio value="replace">replace</a-radio>
          </a-radio-group>
        </a-form-item>
        <a-form-item label="文件">
          <a-upload :auto-upload="false" :limit="1" accept=".csv,.xlsx" @change="onImportFileChange" />
        </a-form-item>
      </div>
    </a-modal>

    <a-drawer v-model:visible="searchVisible" title="FAQ 检索测试" width="520px">
      <div class="modal-form faq-search-test-panel">
        <a-form-item label="问题">
          <a-input-search v-model="searchForm.query" search-button placeholder="输入要测试的用户问题" @search="runFaqSearch" />
        </a-form-item>
        <a-form-item label="返回数量">
          <a-input-number v-model="searchForm.topK" :min="1" :max="20" />
        </a-form-item>
        <a-form-item label="启用重排">
          <a-switch v-model="searchForm.enableRerank" />
        </a-form-item>
        <a-button type="primary" :loading="searching" @click="runFaqSearch">运行检索</a-button>
        <div class="faq-search-results">
          <article v-for="hit in kbStore.faqSearchHits" :key="hit.chunk_id" class="faq-search-hit">
            <header>
              <strong>{{ hit.title || "FAQ 命中" }}</strong>
              <a-tag color="blue">score {{ hit.score.toFixed(3) }}</a-tag>
            </header>
            <p>{{ hit.content }}</p>
            <small>{{ hit.retrieval_method || "unknown" }} · {{ hit.chunk_type || "faq" }}</small>
          </article>
          <a-empty v-if="!kbStore.faqSearchHits.length" description="暂无检索结果" />
        </div>
      </div>
    </a-drawer>
  </main>
</template>
