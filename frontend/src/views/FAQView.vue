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
const batchTagId = ref("");
const batchUpdating = ref(false);
const selectedFaqIdSet = computed(() => new Set(kbStore.selectedFaqIds));
const allVisibleFaqsSelected = computed(() => (
  kbStore.faqs.length > 0 && kbStore.faqs.every((item) => selectedFaqIdSet.value.has(item.id))
));
const form = reactive({
  question: "",
  similarQuestionsText: "",
  answer: "",
  metadataText: "{}",
  tag_id: "",
  enabled: true,
  is_recommended: false,
});
const searchForm = reactive({
  query: "",
  topK: 5,
  enableRerank: false,
});

function openCreate() {
  editing.value = null;
  form.question = "";
  form.similarQuestionsText = "";
  form.answer = "";
  form.metadataText = "{}";
  form.tag_id = filters.value.tag_id;
  form.enabled = true;
  form.is_recommended = false;
  modalVisible.value = true;
}

function openEdit(record: FAQEntryRead) {
  editing.value = record;
  form.question = record.question;
  form.similarQuestionsText = (record.similar_questions || []).join("\n");
  form.answer = record.answer;
  form.metadataText = JSON.stringify(record.metadata || {}, null, 2);
  form.tag_id = record.tag_id || "";
  form.enabled = record.enabled;
  form.is_recommended = record.is_recommended;
  modalVisible.value = true;
}

function metadataPayload() {
  try {
    return JSON.parse(form.metadataText || "{}");
  } catch {
    throw new Error("metadata 必须是合法 JSON");
  }
}

function parseSimilarQuestions() {
  const seen = new Set<string>();
  return form.similarQuestionsText
    .split(/\n|##/)
    .map((item) => item.trim())
    .filter((item) => {
      if (!item || item === form.question.trim() || seen.has(item)) return false;
      seen.add(item);
      return true;
    });
}

async function submit() {
  saving.value = true;
  try {
    const payload = {
      question: form.question,
      similar_questions: parseSimilarQuestions(),
      answer: form.answer,
      metadata: metadataPayload(),
      tag_id: form.tag_id || null,
      enabled: form.enabled,
      is_recommended: form.is_recommended,
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

function toggleFaqSelected(record: FAQEntryRead, checked: boolean) {
  const next = new Set(kbStore.selectedFaqIds);
  if (checked) {
    next.add(record.id);
  } else {
    next.delete(record.id);
  }
  kbStore.selectedFaqIds = Array.from(next);
}

function toggleAllFaqs(checked: boolean) {
  kbStore.selectedFaqIds = checked ? kbStore.faqs.map((item) => item.id) : [];
}

async function batchUpdateSelected(fields: { enabled?: boolean; is_recommended?: boolean; tag_id?: string | null }, message: string) {
  if (!kbStore.selectedFaqIds.length) {
    Message.warning("请先选择 FAQ 条目");
    return;
  }
  batchUpdating.value = true;
  try {
    const byId = Object.fromEntries(kbStore.selectedFaqIds.map((id) => [id, fields]));
    const result = await kbStore.batchUpdateFaqFields(kbId.value, { by_id: byId });
    await refreshFaqs();
    if (result.failed) {
      Message.warning(result.error_summary || `已更新 ${result.succeeded} 条，失败 ${result.failed} 条`);
    } else {
      Message.success(message);
    }
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  } finally {
    batchUpdating.value = false;
  }
}

async function batchSetTag() {
  await batchUpdateSelected({ tag_id: batchTagId.value || null }, "FAQ 标签已批量更新");
  batchTagId.value = "";
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
    kbStore.loadFaqImportLastResult(kbId.value),
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

async function closeImportResult() {
  try {
    await kbStore.closeFaqImportLastResult(kbId.value);
    Message.success("导入结果提示已关闭");
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
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

    <section
      v-if="kbStore.latestFaqImportResult && kbStore.latestFaqImportResult.display_status !== 'close'"
      class="content-card faq-import-summary"
      data-testid="last-import-result"
    >
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
        <a-button size="small" @click="closeImportResult">关闭提示</a-button>
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
      <div class="faq-batch-toolbar" data-testid="batch-update-faq-fields">
        <span>已选 {{ kbStore.selectedFaqIds.length }} 条</span>
        <a-button size="small" :loading="batchUpdating" @click="batchUpdateSelected({ enabled: true }, 'FAQ 已批量启用')">
          批量启用
        </a-button>
        <a-button size="small" :loading="batchUpdating" @click="batchUpdateSelected({ enabled: false }, 'FAQ 已批量停用')">
          批量停用
        </a-button>
        <a-button
          size="small"
          :loading="batchUpdating"
          @click="batchUpdateSelected({ is_recommended: true }, 'FAQ 已批量推荐')"
        >
          批量推荐
        </a-button>
        <a-button
          size="small"
          :loading="batchUpdating"
          @click="batchUpdateSelected({ is_recommended: false }, 'FAQ 已取消推荐')"
        >
          取消推荐
        </a-button>
        <a-select v-model="batchTagId" allow-clear size="small" placeholder="批量标签" class="compact-select">
          <a-option value="">未分类</a-option>
          <a-option v-for="tag in kbStore.tags" :key="tag.id" :value="tag.id">{{ tag.name }}</a-option>
        </a-select>
        <a-button size="small" :loading="batchUpdating" @click="batchSetTag">批量标签</a-button>
      </div>
      <a-table :data="kbStore.faqs" :pagination="false" row-key="id">
        <template #empty>
          <a-empty description="暂无 FAQ 条目" />
        </template>
        <template #columns>
          <a-table-column title="选择" :width="76">
            <template #title>
              <a-checkbox :model-value="allVisibleFaqsSelected" @change="(checked) => toggleAllFaqs(Boolean(checked))" />
            </template>
            <template #cell="{ record }">
              <a-checkbox
                :model-value="selectedFaqIdSet.has(record.id)"
                @change="(checked) => toggleFaqSelected(record, Boolean(checked))"
              />
            </template>
          </a-table-column>
          <a-table-column title="问题" data-index="question" />
          <a-table-column title="相似问法">
            <template #cell="{ record }">
              <div v-if="record.similar_questions?.length" class="similar-question-list">
                <a-tag v-for="question in record.similar_questions" :key="question" color="blue">
                  {{ question }}
                </a-tag>
              </div>
              <span v-else class="muted-text">未设置</span>
            </template>
          </a-table-column>
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
          <a-table-column title="推荐">
            <template #cell="{ record }">
              <a-tag :color="record.is_recommended ? 'orange' : 'gray'">
                {{ record.is_recommended ? "推荐" : "普通" }}
              </a-tag>
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
        <a-form-item label="相似问法">
          <a-textarea
            v-model="form.similarQuestionsText"
            placeholder="一行一个，或使用 ## 分隔"
            :auto-size="{ minRows: 3, maxRows: 6 }"
          />
        </a-form-item>
        <a-form-item label="答案"><a-textarea v-model="form.answer" :auto-size="{ minRows: 4, maxRows: 8 }" /></a-form-item>
        <a-form-item label="标签">
          <a-select v-model="form.tag_id" allow-clear placeholder="未分类">
            <a-option value="">未分类</a-option>
            <a-option v-for="tag in kbStore.tags" :key="tag.id" :value="tag.id">{{ tag.name }}</a-option>
          </a-select>
        </a-form-item>
        <a-form-item label="metadata"><a-textarea v-model="form.metadataText" :auto-size="{ minRows: 3, maxRows: 6 }" /></a-form-item>
        <a-form-item label="启用"><a-switch v-model="form.enabled" /></a-form-item>
        <a-form-item label="推荐"><a-switch v-model="form.is_recommended" /></a-form-item>
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
        <p class="muted-text">导入/导出列包含 question、similar_questions、answer、metadata、enabled、tag_id。</p>
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
            <p v-if="hit.metadata?.matched_question" class="matched-question">
              命中问法：{{ hit.metadata.matched_question }}
            </p>
            <small>{{ hit.retrieval_method || "unknown" }} · {{ hit.chunk_type || "faq" }}</small>
          </article>
          <a-empty v-if="!kbStore.faqSearchHits.length" description="暂无检索结果" />
        </div>
      </div>
    </a-drawer>
  </main>
</template>

<style scoped>
.faq-batch-toolbar {
  align-items: center;
  border-top: 1px solid #e5e7eb;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
  padding-top: 12px;
}

.similar-question-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
</style>
