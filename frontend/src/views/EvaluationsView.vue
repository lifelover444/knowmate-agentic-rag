<script setup lang="ts">
import { Message } from "@arco-design/web-vue";
import { computed, onMounted, reactive, watch } from "vue";
import { useEvaluationStore } from "../stores/evaluations";
import { useKnowledgeBaseStore } from "../stores/knowledgeBase";
import type { EvaluationMetricSummary, EvaluationRunRead, EvaluationSampleRead } from "../types/api";
import { formatApiError } from "../utils/api";

const evaluations = useEvaluationStore();
const kbStore = useKnowledgeBaseStore();

const createForm = reactive({
  knowledge_base_id: "",
  testset_id: "",
  testset_size: 10,
  top_k: 5,
  enable_rerank: false,
});

const activeRun = computed(() => evaluations.currentRun || evaluations.runs[0] || null);
const activeRunId = computed(() => activeRun.value?.id || "");
const metricItems = computed(() => {
  const metrics = activeRun.value?.metrics_summary?.metrics || {};
  const order = ["context_precision", "context_recall", "faithfulness", "response_relevancy", "factual_correctness"];
  return order.map((key) => ({
    key,
    label: metricLabel(key, metrics[key]),
    value: Number(metrics[key]?.average || 0),
    count: Number(metrics[key]?.count || 0),
  }));
});
const overallScore = computed(() => Number(activeRun.value?.metrics_summary?.overall_score || 0));
const baselineScore = computed(() => Number(activeRun.value?.baseline_metrics_summary?.overall_score || 0));
const comparisonItems = computed(() => {
  const metrics = activeRun.value?.comparison?.metrics || {};
  return metricItems.value.map((metric) => ({
    ...metric,
    delta: Number(metrics[metric.key]?.delta || 0),
    baseline: Number(metrics[metric.key]?.baseline || 0),
  }));
});
const sampleRows = computed(() => evaluations.currentRun?.samples || []);
const modelConfig = computed(() => activeRun.value?.model_config || {});

let bootstrapping = false;

watch(
  () => createForm.knowledge_base_id,
  (kbId) => {
    if (bootstrapping) return;
    loadRunsForKnowledgeBase(kbId).catch((error) => Message.error(formatApiError(error)));
  },
);

async function loadRunsForKnowledgeBase(kbId: string) {
  if (!kbId) {
    evaluations.currentRun = null;
    evaluations.testsets = [];
    return;
  }
  const [runs, testsets] = await Promise.all([evaluations.loadEvaluations(kbId), evaluations.loadTestsets(kbId)]);
  if (!testsets.some((testset) => testset.id === createForm.testset_id)) {
    createForm.testset_id = "";
  }
  if (runs[0]) {
    await evaluations.loadEvaluation(runs[0].id);
  } else {
    evaluations.currentRun = null;
  }
}

async function bootstrap() {
  bootstrapping = true;
  try {
    await kbStore.loadKnowledgeBases();
    const latestRuns = await evaluations.loadEvaluations();
    const latestRunKb = latestRuns[0]
      ? kbStore.knowledgeBases.find((kb) => kb.id === latestRuns[0].knowledge_base_id)
      : null;
    createForm.knowledge_base_id = latestRunKb?.id || kbStore.knowledgeBases[0]?.id || "";
    await loadRunsForKnowledgeBase(createForm.knowledge_base_id);
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  } finally {
    bootstrapping = false;
  }
}

async function submitEvaluation() {
  try {
    const run = await evaluations.createEvaluation({
      knowledge_base_id: createForm.knowledge_base_id,
      testset_size: createForm.testset_size,
      top_k: createForm.top_k,
      enable_rerank: createForm.enable_rerank,
      testset_id: createForm.testset_id || null,
    });
    Message.success("RAGas 评测已创建，正在生成测试集。");
    await evaluations.pollEvaluation(run.id);
    await evaluations.loadEvaluations(createForm.knowledge_base_id);
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

async function markActiveBaseline() {
  if (!activeRun.value) return;
  try {
    await evaluations.markBaseline(activeRun.value.id);
    Message.success("已设为基线运行。");
    await loadRunsForKnowledgeBase(createForm.knowledge_base_id);
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

async function openRun(run: EvaluationRunRead) {
  try {
    await evaluations.loadEvaluation(run.id);
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

function metricLabel(key: string, summary?: EvaluationMetricSummary): string {
  const labels: Record<string, string> = {
    context_precision: "上下文精确率",
    context_recall: "上下文召回率",
    faithfulness: "忠实度",
    response_relevancy: "回答相关性",
    factual_correctness: "事实正确性",
  };
  return summary?.label || labels[key] || key;
}

function percent(value: number): string {
  return `${Math.round(Math.max(0, Math.min(1, value)) * 100)}%`;
}

function scoreText(value: number | null | undefined): string {
  if (value === null || value === undefined) return "-";
  return Number(value).toFixed(3);
}

function deltaText(value: number | null | undefined): string {
  const score = Number(value || 0);
  if (!score) return "+0.000";
  return `${score > 0 ? "+" : ""}${score.toFixed(3)}`;
}

function deltaClass(value: number | null | undefined): string {
  const score = Number(value || 0);
  if (score > 0) return "positive";
  if (score < 0) return "negative";
  return "neutral";
}

function statusText(status: string): string {
  if (status === "queued") return "排队中";
  if (status === "processing") return "评测中";
  if (status === "completed") return "已完成";
  if (status === "failed") return "失败";
  return status || "未知";
}

function statusColor(status: string): string {
  if (status === "completed") return "green";
  if (status === "failed") return "red";
  if (status === "processing") return "blue";
  if (status === "queued") return "gold";
  return "gray";
}

function sampleScore(sample: EvaluationSampleRead, key: string): number {
  return Number(sample.scores?.[key] || 0);
}

function diagnosticText(sample: EvaluationSampleRead): string {
  return String(sample.diagnostics?.primary_reason || "暂无诊断");
}

function expectedHitText(sample: EvaluationSampleRead): string {
  const hit = sample.diagnostics?.expected_source_hit;
  if (hit === true) return "命中";
  if (hit === false) return "未命中";
  return sample.expected_chunk_ids.length ? "待诊断" : "无 expected source";
}

function diagnosticListText(sample: EvaluationSampleRead, key: string): string {
  const value = sample.diagnostics?.[key];
  return Array.isArray(value) && value.length ? value.map(String).join(", ") : "无";
}

function modelName(kind: "qa_model" | "embedding_model"): string {
  const item = modelConfig.value[kind] as Record<string, unknown> | undefined;
  if (!item) return "未记录";
  const model = String(item.model_name || item.name || "未记录");
  const last4 = item.api_key_last4 ? ` · key ****${String(item.api_key_last4)}` : "";
  return `${model}${last4}`;
}

onMounted(bootstrap);
</script>

<template>
  <main class="page-shell evaluation-shell">
    <a-page-header title="RAGas 评测" subtitle="按知识库生成测试集，量化 Quick Q&A 的检索、上下文和回答质量。" />

    <section class="content-card evaluation-control">
      <div class="section-heading">
        <div>
          <h2>创建评测</h2>
          <p>复用知识库绑定的 KnowledgeQA 与 Embedding 模型，API Key 只在后端参与调用。</p>
        </div>
      </div>
      <div class="evaluation-form">
        <a-select v-model="createForm.knowledge_base_id" placeholder="选择知识库">
          <a-option v-for="kb in kbStore.knowledgeBases" :key="kb.id" :value="kb.id">
            {{ kb.name }} · {{ kb.chunk_count }} chunks
          </a-option>
        </a-select>
        <a-select v-model="createForm.testset_id" placeholder="黄金测试集（可选）" allow-clear :loading="evaluations.loadingTestsets">
          <a-option v-for="testset in evaluations.testsets" :key="testset.id" :value="testset.id">
            {{ testset.name }} · {{ testset.item_count }} 题
          </a-option>
        </a-select>
        <a-input-number v-model="createForm.testset_size" :min="3" :max="100" />
        <a-input-number v-model="createForm.top_k" :min="1" :max="20" />
        <a-switch v-model="createForm.enable_rerank">
          <template #checked>重排</template>
          <template #unchecked>不重排</template>
        </a-switch>
        <a-button
          type="primary"
          :loading="evaluations.creating || evaluations.polling"
          :disabled="!createForm.knowledge_base_id"
          @click="submitEvaluation"
        >
          创建评测
        </a-button>
      </div>
    </section>

    <section class="evaluation-grid">
      <aside class="content-card evaluation-runs">
        <div class="section-heading">
          <div>
            <h2>评测运行</h2>
            <p>{{ evaluations.runs.length }} 次运行；点击查看量化结果。</p>
          </div>
        </div>
        <div class="evaluation-run-list">
          <button
            v-for="run in evaluations.runs"
            :key="run.id"
            type="button"
            :class="{ active: activeRunId === run.id }"
            @click="openRun(run)"
          >
            <strong>{{ run.knowledge_base_name || run.knowledge_base_id }}</strong>
            <span>{{ new Date(run.created_at).toLocaleString("zh-CN") }}</span>
            <a-tag :color="statusColor(run.status)">{{ statusText(run.status) }}</a-tag>
            <a-tag v-if="run.is_baseline" color="arcoblue">基线运行</a-tag>
          </button>
          <a-empty v-if="!evaluations.loading && !evaluations.runs.length" description="暂无 RAGas 评测" />
        </div>
      </aside>

      <section class="evaluation-main">
        <section class="content-card evaluation-summary">
          <div class="summary-score">
            <span>当前运行总分</span>
            <strong>{{ scoreText(overallScore) }}</strong>
            <a-tag v-if="activeRun" :color="statusColor(activeRun.status)">{{ statusText(activeRun.status) }}</a-tag>
          </div>
          <div class="summary-meta">
            <span>样本 {{ activeRun?.completed_sample_count || 0 }} / {{ activeRun?.sample_count || 0 }}</span>
            <span>失败 {{ activeRun?.failed_sample_count || 0 }}</span>
            <span>题集 {{ activeRun?.testset_source === "golden" ? "黄金测试集" : "chunk-derived" }}</span>
            <span>指标版本 {{ activeRun?.metric_version || "-" }}</span>
            <span>QA {{ modelName("qa_model") }}</span>
            <span>Embedding {{ modelName("embedding_model") }}</span>
          </div>
          <div class="baseline-strip">
            <span>基线运行</span>
            <strong>{{ activeRun?.baseline_run_id ? scoreText(baselineScore) : "未设置" }}</strong>
            <small v-if="activeRun?.comparison?.overall" :class="deltaClass(activeRun.comparison.overall.delta)">
              {{ deltaText(activeRun.comparison.overall.delta) }}
            </small>
            <a-button size="small" :disabled="!activeRun || activeRun.status !== 'completed'" @click="markActiveBaseline">
              设为基线
            </a-button>
          </div>
          <a-alert v-if="activeRun?.error_message" type="error" :content="activeRun.error_message" />
        </section>

        <section class="content-card evaluation-metrics">
          <div class="section-heading">
            <div>
              <h2>量化结果</h2>
              <p>五项 RAGas 指标均按 0-1 保存，条形越长代表当前运行得分越高。</p>
            </div>
          </div>
          <div class="metric-bars">
            <article v-for="metric in comparisonItems" :key="metric.key">
              <header>
                <strong>{{ metric.label }}</strong>
                <span>
                  {{ scoreText(metric.value) }}
                  <small v-if="activeRun?.baseline_run_id" :class="deltaClass(metric.delta)">
                    {{ deltaText(metric.delta) }}
                  </small>
                </span>
              </header>
              <div class="metric-bar">
                <span :style="{ width: percent(metric.value) }"></span>
              </div>
              <small>{{ metric.count }} 个样本参与评分；基线 {{ scoreText(metric.baseline) }}</small>
            </article>
          </div>
        </section>

        <section class="content-card evaluation-heatmap">
          <div class="section-heading">
            <div>
              <h2>逐题明细</h2>
              <p>每行保留问题、参考答案、回答、RAGas 分数和 source 明细。</p>
            </div>
          </div>
          <a-table :data="sampleRows" :pagination="false" row-key="id" :scroll="{ x: 1280 }">
            <template #columns>
              <a-table-column title="#" :width="58">
                <template #cell="{ record }">{{ record.sample_index + 1 }}</template>
              </a-table-column>
              <a-table-column title="问题" :width="260">
                <template #cell="{ record }">
                  <div class="sample-question">
                    <strong>{{ record.user_input }}</strong>
                    <small>{{ record.synthesizer_name || "RAGas" }}</small>
                  </div>
                </template>
              </a-table-column>
              <a-table-column v-for="metric in metricItems" :key="metric.key" :title="metric.label" :width="128">
                <template #cell="{ record }">
                  <span class="heat-cell" :style="{ '--score': sampleScore(record, metric.key) }">
                    {{ scoreText(sampleScore(record, metric.key)) }}
                  </span>
                </template>
              </a-table-column>
              <a-table-column title="expected source" :width="140">
                <template #cell="{ record }">
                  <a-tag :color="record.diagnostics?.expected_source_hit === false ? 'red' : 'green'">
                    {{ expectedHitText(record) }}
                  </a-tag>
                </template>
              </a-table-column>
              <a-table-column title="诊断" :width="150">
                <template #cell="{ record }">
                  <span class="diagnostic-pill">{{ diagnosticText(record) }}</span>
                </template>
              </a-table-column>
              <a-table-column title="状态" :width="96">
                <template #cell="{ record }">
                  <a-tag :color="statusColor(record.status)">{{ statusText(record.status) }}</a-tag>
                </template>
              </a-table-column>
            </template>
          </a-table>

          <a-collapse v-if="sampleRows.length" class="sample-detail-list">
            <a-collapse-item v-for="sample in sampleRows" :key="sample.id" :header="`问题 ${sample.sample_index + 1} source 明细`">
              <div class="sample-detail">
                <section>
                  <strong>参考答案</strong>
                  <p>{{ sample.reference || "未生成参考答案" }}</p>
                </section>
                <section>
                  <strong>实际回答</strong>
                  <p>{{ sample.response || sample.error_message || "暂无回答" }}</p>
                </section>
                <section>
                  <strong>sources</strong>
                  <div class="source-detail-list">
                    <article v-for="source in sample.sources" :key="source.chunk_id">
                      <header>
                        <span>{{ source.title || source.document_title || source.document_id }}</span>
                        <small>{{ scoreText(source.score) }}</small>
                      </header>
                      <p>{{ source.context_content || source.content || source.snippet }}</p>
                    </article>
                    <a-empty v-if="!sample.sources.length" description="没有 source 明细" />
                  </div>
                </section>
                <section>
                  <strong>诊断</strong>
                  <p>
                    expected source：{{ sample.expected_chunk_ids.join(", ") || "无" }}
                    missed：{{ diagnosticListText(sample, "missed_chunk_ids") }}
                    retrieved：{{ diagnosticListText(sample, "retrieved_chunk_ids") }}
                    低分指标：{{ diagnosticListText(sample, "low_score_metrics") }}
                  </p>
                </section>
              </div>
            </a-collapse-item>
          </a-collapse>
        </section>
      </section>
    </section>
  </main>
</template>

<style scoped>
.evaluation-shell {
  gap: 14px;
}

.evaluation-control {
  display: grid;
  gap: 12px;
}

.evaluation-form {
  display: grid;
  grid-template-columns: minmax(220px, 1.4fr) minmax(180px, 1fr) minmax(120px, 0.55fr) minmax(110px, 0.5fr) auto auto;
  gap: 10px;
  align-items: center;
}

.evaluation-grid {
  display: grid;
  grid-template-columns: minmax(240px, 320px) minmax(0, 1fr);
  gap: 14px;
  align-items: start;
}

.evaluation-runs {
  position: sticky;
  top: 18px;
  display: grid;
  gap: 12px;
}

.evaluation-run-list {
  display: grid;
  gap: 8px;
}

.evaluation-run-list button {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 5px 8px;
  align-items: center;
  border: 1px solid var(--km-border);
  border-radius: var(--km-radius);
  padding: 10px 12px;
  color: var(--km-text-primary);
  background: #fbfdfc;
  text-align: left;
  cursor: pointer;
}

.evaluation-run-list button.active,
.evaluation-run-list button:hover {
  border-color: rgba(22, 199, 132, 0.35);
  background: var(--km-bg-deep);
}

.evaluation-run-list span {
  color: var(--km-text-secondary);
  font-size: 12px;
}

.evaluation-main {
  display: grid;
  gap: 14px;
}

.evaluation-summary {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 18px;
  align-items: center;
}

.summary-score {
  display: grid;
  gap: 4px;
}

.summary-score span,
.summary-meta span {
  color: var(--km-text-secondary);
  font-size: 12px;
}

.summary-score strong {
  font-size: 40px;
  line-height: 1;
}

.summary-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.summary-meta span {
  border: 1px solid var(--km-border);
  border-radius: var(--km-radius);
  padding: 7px 9px;
  background: #fbfdfc;
}

.baseline-strip {
  display: grid;
  grid-template-columns: auto auto auto auto;
  gap: 8px;
  align-items: center;
  justify-content: start;
}

.baseline-strip span,
.baseline-strip small,
.metric-bars header small {
  color: var(--km-text-secondary);
}

.baseline-strip strong {
  font-size: 18px;
}

.positive {
  color: #00a870 !important;
}

.negative {
  color: #d54941 !important;
}

.neutral {
  color: var(--km-text-secondary) !important;
}

.metric-bars {
  display: grid;
  gap: 12px;
}

.metric-bars article {
  display: grid;
  gap: 7px;
}

.metric-bars header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.metric-bars small {
  color: var(--km-text-secondary);
}

.metric-bar {
  height: 10px;
  overflow: hidden;
  border-radius: 999px;
  background: #edf0f2;
}

.metric-bar span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #16c784, #2080f0);
}

.sample-question {
  display: grid;
  gap: 4px;
}

.sample-question small {
  color: var(--km-text-secondary);
}

.heat-cell {
  display: inline-flex;
  min-width: 70px;
  border-radius: var(--km-radius);
  padding: 5px 8px;
  color: #1f2329;
  background: color-mix(in srgb, var(--km-primary) calc(var(--score) * 70%), #f1f3f5);
  font-variant-numeric: tabular-nums;
}

.diagnostic-pill {
  display: inline-flex;
  border-radius: var(--km-radius);
  padding: 5px 8px;
  color: var(--km-text-primary);
  background: #f1f7f4;
}

.sample-detail-list {
  margin-top: 14px;
}

.sample-detail {
  display: grid;
  gap: 14px;
}

.sample-detail section {
  display: grid;
  gap: 6px;
}

.sample-detail p {
  color: var(--km-text-secondary);
  line-height: 1.65;
  white-space: pre-wrap;
}

.source-detail-list {
  display: grid;
  gap: 8px;
}

.source-detail-list article {
  display: grid;
  gap: 6px;
  border: 1px solid var(--km-border);
  border-radius: var(--km-radius);
  padding: 10px 12px;
  background: #fbfdfc;
}

.source-detail-list header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.source-detail-list small {
  color: var(--km-text-secondary);
}

@media (max-width: 980px) {
  .evaluation-form,
  .evaluation-grid,
  .baseline-strip,
  .evaluation-summary {
    grid-template-columns: 1fr;
  }

  .evaluation-runs {
    position: static;
  }
}
</style>
