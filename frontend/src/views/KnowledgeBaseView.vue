<script setup lang="ts">
import { Message } from "@arco-design/web-vue";
import { onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { useKnowledgeBaseStore } from "../stores/knowledgeBase";
import { useModelsStore } from "../stores/models";
import { useRetrievalStore } from "../stores/retrieval";
import { formatApiError } from "../utils/api";

const router = useRouter();
const kbStore = useKnowledgeBaseStore();
const modelStore = useModelsStore();
const retrieval = useRetrievalStore();
const createVisible = ref(false);
const creating = ref(false);

const createForm = reactive({
  name: "",
  description: "",
  embedding_model_id: "",
  summary_model_id: "",
});

function openCreateModal() {
  createForm.name = `知友知识库-${new Date().toLocaleTimeString("zh-CN", { hour12: false })}`;
  createForm.description = "";
  createForm.embedding_model_id = modelStore.selectedEmbeddingModelId;
  createForm.summary_model_id = modelStore.selectedChatModelId;
  createVisible.value = true;
}

async function submitCreate() {
  creating.value = true;
  try {
    const created = await kbStore.createKnowledgeBase({
      name: createForm.name,
      description: createForm.description,
      embedding_model_id: createForm.embedding_model_id,
      summary_model_id: createForm.summary_model_id,
      chunking_config: retrieval.chunkingPayload(),
      parser_engine_rules: retrieval.parserEngineRulesPayload(),
    });
    createVisible.value = false;
    Message.success("知识库已创建");
    router.push(`/knowledge-bases/${created.id}/documents`);
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  } finally {
    creating.value = false;
  }
}

async function deleteKb(kbId: string) {
  try {
    await kbStore.deleteKnowledgeBase(kbId);
    Message.success("知识库已删除");
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

onMounted(() => {
  Promise.all([
    kbStore.loadKnowledgeBases(),
    modelStore.loadModels(),
    retrieval.loadParserEngines(),
  ]).catch((error) => {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  });
});
</script>

<template>
  <main class="page-shell">
    <a-page-header title="知识库" subtitle="知识库优先管理文档、解析切分规则和模型绑定。">
      <template #extra>
        <a-button type="primary" data-testid="create-kb" @click="openCreateModal">创建知识库</a-button>
      </template>
    </a-page-header>

    <section class="content-card">
      <a-table :data="kbStore.knowledgeBases" :loading="kbStore.loading" :pagination="false" row-key="id">
        <template #columns>
          <a-table-column title="名称" data-index="name" />
          <a-table-column title="描述" data-index="description" />
          <a-table-column title="文档">
            <template #cell="{ record }">{{ record.document_count }} / {{ record.chunk_count }} chunks</template>
          </a-table-column>
          <a-table-column title="模型">
            <template #cell="{ record }">
              <div class="table-stack">
                <span>embedding_model_id: {{ record.embedding_model_id }}</span>
                <span>summary_model_id: {{ record.summary_model_id }}</span>
              </div>
            </template>
          </a-table-column>
          <a-table-column title="操作">
            <template #cell="{ record }">
              <a-space>
                <a-button size="mini" type="primary" @click="router.push(`/knowledge-bases/${record.id}/documents`)">
                  文档管理
                </a-button>
                <a-popconfirm content="确认删除这个知识库？" type="warning" @ok="deleteKb(record.id)">
                  <a-button size="mini" status="danger">删除</a-button>
                </a-popconfirm>
              </a-space>
            </template>
          </a-table-column>
        </template>
      </a-table>
      <a-empty v-if="!kbStore.loading && !kbStore.knowledgeBases.length" description="暂无知识库" />
    </section>

    <a-modal v-model:visible="createVisible" title="创建知识库" :confirm-loading="creating" @ok="submitCreate">
      <div class="modal-form">
        <a-form-item label="名称">
          <a-input v-model="createForm.name" data-testid="kb-name" />
        </a-form-item>
        <a-form-item label="描述">
          <a-textarea v-model="createForm.description" data-testid="kb-description" :auto-size="{ minRows: 3, maxRows: 5 }" />
        </a-form-item>
        <a-form-item label="Embedding 模型">
          <a-select v-model="createForm.embedding_model_id" data-testid="embedding-model-select">
            <a-option v-for="model in modelStore.embeddingModels" :key="model.id" :value="model.id">
              {{ model.name }} · {{ model.model_name }}
            </a-option>
          </a-select>
        </a-form-item>
        <a-form-item label="QA 模型">
          <a-select v-model="createForm.summary_model_id" data-testid="qa-model-select">
            <a-option v-for="model in modelStore.chatModels" :key="model.id" :value="model.id">
              {{ model.name }} · {{ model.model_name }}
            </a-option>
          </a-select>
        </a-form-item>
        <a-divider>切分配置</a-divider>
        <div class="form-grid form-grid--compact">
          <a-form-item label="策略">
            <a-select v-model="retrieval.chunkStrategy" data-testid="chunk-strategy">
              <a-option value="auto">auto</a-option>
              <a-option value="heading">heading</a-option>
              <a-option value="heuristic">heuristic</a-option>
              <a-option value="legacy">legacy</a-option>
            </a-select>
          </a-form-item>
          <a-form-item label="chunk size">
            <a-input-number v-model="retrieval.chunkSize" data-testid="chunk-size" />
          </a-form-item>
          <a-form-item label="overlap">
            <a-input-number v-model="retrieval.chunkOverlap" data-testid="chunk-overlap" />
          </a-form-item>
          <a-form-item label="separators">
            <a-input v-model="retrieval.separatorsText" data-testid="chunk-separators" />
          </a-form-item>
          <a-form-item label="token limit">
            <a-input-number v-model="retrieval.tokenLimit" data-testid="token-limit" />
          </a-form-item>
          <a-form-item label="languages">
            <a-input v-model="retrieval.languagesText" data-testid="chunk-languages" />
          </a-form-item>
          <a-form-item label="parent-child">
            <a-switch v-model="retrieval.enableParentChild" data-testid="enable-parent-child" />
          </a-form-item>
          <a-form-item label="parent size">
            <a-input-number v-model="retrieval.parentChunkSize" data-testid="parent-chunk-size" />
          </a-form-item>
          <a-form-item label="child size">
            <a-input-number v-model="retrieval.childChunkSize" data-testid="child-chunk-size" />
          </a-form-item>
        </div>
        <a-alert type="info" content="创建 payload 将包含 chunking_config 与 parser_engine_rules。" />
      </div>
    </a-modal>
  </main>
</template>
