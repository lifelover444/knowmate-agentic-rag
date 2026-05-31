# TASK-006 FAQ Import Export And Search Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a WeKnora-like FAQ workbench surface for CSV/XLSX import, export, import result summaries, and FAQ-only retrieval testing.

**Architecture:** Keep backend unchanged for this task and consume the APIs delivered in `TASK-005`. Extend the existing Pinia knowledge-base store as the frontend boundary, then keep `FAQView.vue` focused on workflow state and UI rendering.

**Tech Stack:** Vue 3, Pinia, TypeScript, Arco Design Vue, FastAPI-backed `/api/v1`, pytest frontend source checks, Vite build.

---

## WeKnora Reference Points

- `D:/myproject/_references/WeKnora/frontend/src/views/knowledge/components/FAQEntryManager.vue`
  - FAQ toolbar has create/import, export, and search-test actions.
  - Import result card shows total/success/failed/skipped and failure reasons.
  - Search test drawer accepts query, threshold, count, and renders scored FAQ hits.
- `D:/myproject/_references/WeKnora/frontend/src/api/knowledge-base/index.ts`
  - `exportFAQEntries(kbId)` downloads a file.
  - `searchFAQEntries(kbId, data)` posts query text, threshold, and match count.
- `D:/myproject/_references/WeKnora/docs/api/faq.md`
  - WeKnora has a dedicated `/faq/search`; knowmate will use existing `/knowledge-search` for this task and queue dedicated FAQ search backend later if needed.

## File Structure

- Modify `frontend/src/utils/api.ts`
  - Add binary download helper for export endpoints.
  - Keep `formatApiError` behavior so raw objects never render as `[object Object]`.
- Modify `frontend/src/types/api.ts`
  - Add FAQ import result, export format, and search form result types.
- Modify `frontend/src/stores/knowledgeBase.ts`
  - Add `importFaqs`, `exportFaqs`, and `searchFaqKnowledge`.
  - Store latest import summary and latest FAQ search hits.
- Modify `frontend/src/views/FAQView.vue`
  - Add toolbar buttons for import, export CSV, export XLSX, and search test.
  - Add import modal with file picker and append/replace segmented control.
  - Add import summary card with failed row details.
  - Add search test drawer with query, top_k, mode, rerank toggle, and hit rendering.
- Modify `frontend/src/styles/app.css`
  - Add small layout utilities for FAQ toolbar, import summary, failure list, and search results.
- Add `tests/test_frontend_v07_faq_import_export.py`
  - Static/source-level coverage for TASK-006 controls and API wiring.
- Extend `tests/test_frontend_api_errors.py`
  - Add one import-failure shaped payload case to prove no `[object Object]`.

## Task 1: Frontend API Helpers And Types

**Files:**
- Modify: `frontend/src/utils/api.ts`
- Modify: `frontend/src/types/api.ts`
- Test: `tests/test_frontend_v07_faq_import_export.py`

- [ ] **Step 1: Write the failing source test**

Add `tests/test_frontend_v07_faq_import_export.py`:

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_task_006_faq_import_export_and_search_panel_wiring():
    store = read("frontend/src/stores/knowledgeBase.ts")
    view = read("frontend/src/views/FAQView.vue")
    types = read("frontend/src/types/api.ts")
    api = read("frontend/src/utils/api.ts")

    assert "downloadRequest" in api
    assert "FAQImportResult" in types
    assert "FAQSearchTestResult" in types
    assert "importFaqs" in store
    assert "/knowledge-bases/${kbId}/faqs/import" in store
    assert "exportFaqs" in store
    assert "/knowledge-bases/${kbId}/faqs/export" in store
    assert "searchFaqKnowledge" in store
    assert 'mode: "hybrid"' in store
    assert "FAQ 导入" in view
    assert "append" in view
    assert "replace" in view
    assert "导入结果" in view
    assert "失败行" in view
    assert "导出 CSV" in view
    assert "导出 XLSX" in view
    assert "FAQ 检索测试" in view
    assert "kbStore.faqSearchHits" in view
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest tests/test_frontend_v07_faq_import_export.py -q
```

Expected: FAIL because the new file expects missing helper/types/store/view strings.

- [ ] **Step 3: Add API helper**

In `frontend/src/utils/api.ts`, add:

```ts
export async function downloadRequest(path: string): Promise<Blob> {
  const response = await fetch(apiUrl(path));
  if (!response.ok) {
    const text = await response.text();
    throw new Error(formatApiError(parseResponsePayload(text), text || `HTTP ${response.status}`));
  }
  return response.blob();
}
```

- [ ] **Step 4: Add types**

In `frontend/src/types/api.ts`, add:

```ts
export type FAQExportFormat = "csv" | "xlsx";

export interface FAQImportFailure {
  row: number;
  question?: string | null;
  error: string;
}

export interface FAQImportResult {
  total: number;
  imported: number;
  failed: number;
  mode: "append" | "replace";
  failures: FAQImportFailure[];
}

export interface FAQSearchTestResult extends SourceRead {
  tag_id?: string | null;
}
```

- [ ] **Step 5: Run focused test**

Run:

```powershell
python -m pytest tests/test_frontend_v07_faq_import_export.py -q
```

Expected: still FAIL because store and view are not wired yet.

## Task 2: Store Methods

**Files:**
- Modify: `frontend/src/stores/knowledgeBase.ts`
- Test: `tests/test_frontend_v07_faq_import_export.py`

- [ ] **Step 1: Update imports**

Import the download helper and new types:

```ts
import { deleteRequest, downloadRequest, getJson, postForm, postJson, putJson } from "../utils/api";
import type {
  FAQExportFormat,
  FAQImportResult,
  FAQSearchTestResult,
  // existing imports stay
} from "../types/api";
```

- [ ] **Step 2: Add state**

Inside the store setup:

```ts
const latestFaqImportResult = ref<FAQImportResult | null>(null);
const faqSearchHits = ref<FAQSearchTestResult[]>([]);
```

- [ ] **Step 3: Add import/export/search methods**

Add near existing FAQ methods:

```ts
async function importFaqs(kbId: string, file: File, mode: "append" | "replace") {
  const form = new FormData();
  form.append("file", file);
  form.append("mode", mode);
  latestFaqImportResult.value = await postForm<FAQImportResult>(`/knowledge-bases/${kbId}/faqs/import`, form);
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
```

- [ ] **Step 4: Return state and methods**

Add to returned store object:

```ts
latestFaqImportResult,
faqSearchHits,
importFaqs,
exportFaqs,
searchFaqKnowledge,
```

- [ ] **Step 5: Run focused test**

Run:

```powershell
python -m pytest tests/test_frontend_v07_faq_import_export.py -q
```

Expected: still FAIL until `FAQView.vue` is wired.

## Task 3: FAQ View Workflow

**Files:**
- Modify: `frontend/src/views/FAQView.vue`
- Modify: `frontend/src/styles/app.css`
- Test: `tests/test_frontend_v07_faq_import_export.py`

- [ ] **Step 1: Add component state**

In `FAQView.vue` script setup, add:

```ts
const importVisible = ref(false);
const importing = ref(false);
const exportLoading = ref<"csv" | "xlsx" | "">("");
const searchVisible = ref(false);
const searching = ref(false);
const importMode = ref<"append" | "replace">("append");
const selectedImportFile = ref<File | null>(null);
const searchForm = reactive({
  query: "",
  topK: 5,
  enableRerank: false,
});
```

- [ ] **Step 2: Add file and download helpers**

Add:

```ts
function onImportFileChange(_: unknown, currentFile?: { file?: File }) {
  selectedImportFile.value = currentFile?.file || null;
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
```

- [ ] **Step 3: Add submit/export/search actions**

Add:

```ts
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
```

- [ ] **Step 4: Add toolbar controls**

In page header extra actions, add buttons:

```vue
<a-button @click="importVisible = true">FAQ 导入</a-button>
<a-button :loading="exportLoading === 'csv'" @click="exportFaqs('csv')">导出 CSV</a-button>
<a-button :loading="exportLoading === 'xlsx'" @click="exportFaqs('xlsx')">导出 XLSX</a-button>
<a-button @click="searchVisible = true">FAQ 检索测试</a-button>
```

- [ ] **Step 5: Add import result card**

Below the page header, add:

```vue
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
```

- [ ] **Step 6: Add import modal**

Add near existing FAQ modal:

```vue
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
```

- [ ] **Step 7: Add search drawer**

Add:

```vue
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
```

- [ ] **Step 8: Add styles**

In `frontend/src/styles/app.css`, add:

```css
.faq-import-summary,
.faq-search-test-panel {
  margin-bottom: 16px;
}

.faq-import-failures,
.faq-search-results {
  display: grid;
  gap: 10px;
}

.faq-import-failure,
.faq-search-hit {
  border: 1px solid var(--color-border-2);
  border-radius: 8px;
  padding: 12px;
  background: var(--color-fill-1);
}

.faq-search-hit header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
```

- [ ] **Step 9: Run focused frontend source test**

Run:

```powershell
python -m pytest tests/test_frontend_v07_faq_import_export.py -q
```

Expected: PASS.

## Task 4: API Error Formatting Regression

**Files:**
- Modify: `tests/test_frontend_api_errors.py`

- [ ] **Step 1: Add import failure payload assertion**

Extend the Node script to include:

```js
const importMessage = formatApiError({
  detail: {
    failures: [{ row: 2, question: '缺少答案', error: '答案不能为空' }],
  },
});

if (importMessage.includes('[object Object]')) {
  throw new Error(importMessage);
}
if (!importMessage.includes('答案不能为空')) {
  throw new Error(importMessage);
}
```

If current `formatApiError` serializes nested objects as JSON rather than Chinese text, keep JSON as acceptable only if it does not include `[object Object]` and includes the useful error text.

- [ ] **Step 2: Run error formatting test**

Run:

```powershell
python -m pytest tests/test_frontend_api_errors.py -q
```

Expected: PASS.

## Task 5: Build And Broaden Verification

**Files:**
- No additional code changes.

- [ ] **Step 1: Run TASK-006 focused tests**

Run:

```powershell
python -m pytest tests/test_frontend_v07_faq_import_export.py tests/test_frontend_api_errors.py -q
```

Expected: PASS.

- [ ] **Step 2: Run all frontend source checks**

Run:

```powershell
python -m pytest (rg --files tests | rg 'test_frontend_.*\.py$') -q
```

Expected: PASS.

- [ ] **Step 3: Run frontend production build**

Run:

```powershell
npm --prefix frontend run build
```

Expected: Vite build succeeds and `frontend/dist/**` updates.

- [ ] **Step 4: Optional codebase hygiene**

Run if production TypeScript or shared utilities changed in a way that could affect backend test discovery:

```powershell
ruff check .
python -m compileall app tests
```

Expected: PASS.

## Completion Bookkeeping

- [ ] Move `TASK-006` from `## Active` to `docs/ai-loop/done.md`.
- [ ] Record changed files:
  - `frontend/src/utils/api.ts`
  - `frontend/src/types/api.ts`
  - `frontend/src/stores/knowledgeBase.ts`
  - `frontend/src/views/FAQView.vue`
  - `frontend/src/styles/app.css`
  - `tests/test_frontend_v07_faq_import_export.py`
  - `tests/test_frontend_api_errors.py`
  - `frontend/dist/**`
- [ ] Leave `TASK-007` as next queue item.

## Self-Review

- Spec coverage: import, append/replace, export, import failure summary, FAQ search test panel, and frontend error formatting are each covered by a task.
- Placeholder scan: no `TBD`, `TODO`, or unspecified "add tests" steps remain.
- Type consistency: store methods and view references use `latestFaqImportResult`, `faqSearchHits`, `importFaqs`, `exportFaqs`, and `searchFaqKnowledge` consistently.
