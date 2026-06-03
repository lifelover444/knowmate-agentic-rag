<script setup lang="ts">
import { Message } from "@arco-design/web-vue";
import { onMounted } from "vue";
import ModelConfigForm from "../components/ModelConfigForm.vue";
import { useModelsStore } from "../stores/models";
import { formatApiError } from "../utils/api";
import type { ModelPayload, ModelRead, ModelTestPayload } from "../types/api";

const modelStore = useModelsStore();

function saveQaModel() {
  return null;
}

function saveEmbeddingModel() {
  return null;
}

async function saveModel(data: { modelId?: string; payload: ModelPayload }) {
  try {
    await modelStore.saveModel(data.payload, data.modelId);
    Message.success("模型配置已保存");
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

async function testModel(payload: ModelTestPayload) {
  try {
    const result = await modelStore.testModel(payload);
    Message.success(String(result.message || "模型测试完成"));
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

async function deleteModel(model: ModelRead) {
  try {
    await modelStore.deleteModel(model.id);
    Message.success("模型配置已删除");
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

onMounted(() => {
  modelStore.loadModels().catch((error) => {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  });
});
</script>

<template>
  <main class="page-shell">
    <a-page-header title="模型配置" subtitle="集中管理 QA、Embedding 和 Rerank 模型，API Key 只显示配置状态和尾号。" />

    <section class="content-card">
      <a-tabs default-active-key="qa">
        <a-tab-pane key="qa" title="QA 模型">
          <ModelConfigForm
            title="QA 模型"
            model-type="KnowledgeQA"
            :models="modelStore.chatModels"
            :provider-presets="modelStore.providerPresets"
            :selected-model-id="modelStore.selectedChatModelId"
            :saving="modelStore.saving"
            :testing="modelStore.testing"
            @select="modelStore.selectedChatModelId = $event"
            @save="saveModel"
            @test="testModel"
            @delete="(id) => deleteModel(modelStore.models.find((model) => model.id === id)!)"
          />
        </a-tab-pane>
        <a-tab-pane key="embedding" title="Embedding 模型">
          <ModelConfigForm
            title="Embedding 模型"
            model-type="Embedding"
            :models="modelStore.embeddingModels"
            :provider-presets="modelStore.providerPresets"
            :selected-model-id="modelStore.selectedEmbeddingModelId"
            :saving="modelStore.saving"
            :testing="modelStore.testing"
            @select="modelStore.selectedEmbeddingModelId = $event"
            @save="saveModel"
            @test="testModel"
            @delete="(id) => deleteModel(modelStore.models.find((model) => model.id === id)!)"
          />
        </a-tab-pane>
        <a-tab-pane key="rerank" title="Rerank 模型">
          <ModelConfigForm
            title="Rerank 模型"
            model-type="Rerank"
            :models="modelStore.rerankModels"
            :provider-presets="modelStore.providerPresets"
            :selected-model-id="modelStore.selectedRerankModelId"
            :saving="modelStore.saving"
            :testing="modelStore.testing"
            @select="modelStore.selectedRerankModelId = $event"
            @save="saveModel"
            @test="testModel"
            @delete="(id) => deleteModel(modelStore.models.find((model) => model.id === id)!)"
          />
        </a-tab-pane>
      </a-tabs>
    </section>

    <section class="content-card">
      <div class="section-heading">
        <div>
          <h2>模型列表</h2>
          <p>后端不会返回 API Key 明文，只展示是否已配置和尾号。</p>
        </div>
      </div>
      <section v-for="group in modelStore.modelGroups" :key="group.type" class="model-group">
        <h3>{{ group.label }}</h3>
        <a-table :data="group.models" :loading="modelStore.loading" :pagination="false" row-key="id">
          <template #columns>
            <a-table-column title="名称" data-index="name" />
            <a-table-column title="模型" data-index="model_name" />
            <a-table-column title="供应商" data-index="provider" />
            <a-table-column title="API Key">
              <template #cell="{ record }">
                <a-tag :color="record.api_key_configured ? 'green' : 'gray'">
                  {{ record.api_key_configured ? `已配置 ****${record.api_key_last4 || ""}` : "未配置" }}
                </a-tag>
              </template>
            </a-table-column>
            <a-table-column title="操作">
              <template #cell="{ record }">
                <a-popconfirm content="确认删除这个模型？" type="warning" @ok="deleteModel(record)">
                  <a-button size="mini" status="danger">删除</a-button>
                </a-popconfirm>
              </template>
            </a-table-column>
          </template>
        </a-table>
      </section>
    </section>
  </main>
</template>

<style scoped>
.model-group {
  display: grid;
  gap: 10px;
  margin-top: 14px;
}

.model-group h3 {
  margin: 0;
  color: var(--km-text-primary);
  font-size: 15px;
}
</style>
