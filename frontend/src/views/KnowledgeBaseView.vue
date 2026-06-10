<script setup lang="ts">
import { Message } from "@arco-design/web-vue";
import { onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { useKnowledgeBaseStore } from "../stores/knowledgeBase";
import { useModelsStore } from "../stores/models";
import { useRetrievalStore } from "../stores/retrieval";
import type { KnowledgeBaseRead } from "../types/api";
import { formatApiError } from "../utils/api";

const router = useRouter();
const kbStore = useKnowledgeBaseStore();
const modelStore = useModelsStore();
const retrieval = useRetrievalStore();
const createVisible = ref(false);
const editVisible = ref(false);
const creating = ref(false);
const editing = ref(false);
const editingKbId = ref("");

const createForm = reactive({
  name: "",
  description: "",
  kb_type: "document",
  embedding_model_id: "",
  summary_model_id: "",
  enable_parent_child: true,
  enable_rerank: true,
});

const editForm = reactive({
  name: "",
  description: "",
  kb_type: "document",
  embedding_model_id: "",
  summary_model_id: "",
  enable_parent_child: true,
  enable_rerank: true,
});

function openCreateModal() {
  createForm.name = `知友知识库-${new Date().toLocaleTimeString("zh-CN", { hour12: false })}`;
  createForm.description = "";
  createForm.kb_type = "document";
  createForm.embedding_model_id = modelStore.selectedEmbeddingModelId;
  createForm.summary_model_id = modelStore.selectedChatModelId;
  createForm.enable_parent_child = true;
  createForm.enable_rerank = true;
  createVisible.value = true;
}

async function submitCreate() {
  creating.value = true;
  try {
    const created = await kbStore.createKnowledgeBase({
      name: createForm.name,
      description: createForm.description,
      kb_type: createForm.kb_type,
      embedding_model_id: createForm.embedding_model_id,
      summary_model_id: createForm.summary_model_id,
      vector_store_id: null,
      chunking_config: retrieval.chunkingPayload(),
      parser_engine_rules: retrieval.parserEngineRulesPayload(),
      indexing_strategy: {
        enable_vector: true,
        enable_keyword: true,
        enable_parent_child: true,
        enable_rerank: true,
        enable_wiki: false,
        enable_knowledge_graph: false,
      },
    });
    createVisible.value = false;
    Message.success("知识库已创建");
    router.push(`/knowledge-bases/${created.id}`);
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  } finally {
    creating.value = false;
  }
}

function openEditModal(record: any) {
  editingKbId.value = record.id;
  editForm.name = record.name;
  editForm.description = record.description || "";
  editForm.kb_type = record.kb_type || "document";
  editForm.embedding_model_id = record.embedding_model_id;
  editForm.summary_model_id = record.summary_model_id;
  editForm.enable_parent_child = true;
  editForm.enable_rerank = true;
  editVisible.value = true;
}

async function submitEdit() {
  editing.value = true;
  try {
    await kbStore.updateKnowledgeBase(editingKbId.value, {
      name: editForm.name,
      description: editForm.description,
      kb_type: editForm.kb_type,
      embedding_model_id: editForm.embedding_model_id,
      summary_model_id: editForm.summary_model_id,
      vector_store_id: null,
      indexing_strategy: {
        enable_vector: true,
        enable_keyword: true,
        enable_parent_child: true,
        enable_rerank: true,
        enable_wiki: false,
        enable_knowledge_graph: false,
      },
    });
    editVisible.value = false;
    Message.success("知识库配置已更新");
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  } finally {
    editing.value = false;
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

function capabilityItems(record: KnowledgeBaseRead) {
  const capabilities = record.capabilities || {
    document: record.kb_type !== "faq",
    faq: record.kb_type === "faq",
    vector: false,
    keyword: false,
    parent_child: false,
    rerank: false,
    wiki: false,
    graph: false,
  };
  return [
    { key: "document", label: "文档", enabled: Boolean(capabilities.document), color: "green" },
    { key: "faq", label: "FAQ", enabled: Boolean(capabilities.faq), color: "purple" },
    { key: "vector", label: "向量", enabled: Boolean(capabilities.vector), color: "blue" },
    { key: "keyword", label: "关键词", enabled: Boolean(capabilities.keyword), color: "arcoblue" },
    { key: "parent_child", label: "父子块", enabled: Boolean(capabilities.parent_child), color: "cyan" },
    { key: "rerank", label: "重排", enabled: Boolean(capabilities.rerank), color: "orangered" },
    { key: "wiki", label: capabilities.wiki ? "Wiki" : "Wiki 未启用", enabled: Boolean(capabilities.wiki), color: "gray" },
    { key: "graph", label: capabilities.graph ? "Graph" : "Graph 未启用", enabled: Boolean(capabilities.graph), color: "gray" },
  ];
}

async function togglePin(record: KnowledgeBaseRead) {
  const pinned = !record.is_pinned;
  try {
    await kbStore.updateKnowledgeBasePin(record.id, pinned);
    Message.success(pinned ? "知识库已置顶" : "已取消置顶");
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error) || "置顶失败");
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
          <a-table-column title="名称">
            <template #cell="{ record }">
              <div class="kb-name-cell">
                <a-tag v-if="record.is_pinned" color="gold">置顶</a-tag>
                <strong>{{ record.name }}</strong>
                <small v-if="record.pinned_at">pinned_at: {{ new Date(record.pinned_at).toLocaleString("zh-CN") }}</small>
              </div>
            </template>
          </a-table-column>
          <a-table-column title="描述" data-index="description" />
          <a-table-column title="文档">
            <template #cell="{ record }">{{ record.document_count }} / {{ record.chunk_count }} chunks</template>
          </a-table-column>
          <a-table-column title="类型">
            <template #cell="{ record }">
              <a-tag :color="record.kb_type === 'faq' ? 'purple' : 'green'">
                {{ record.kb_type === "faq" ? "FAQ 知识库" : "文档知识库" }}
              </a-tag>
            </template>
          </a-table-column>
          <a-table-column title="模型">
            <template #cell="{ record }">
              <div class="table-stack">
                <span>embedding_model_id: {{ record.embedding_model_id }}</span>
                <span>summary_model_id: {{ record.summary_model_id }}</span>
              </div>
            </template>
          </a-table-column>
          <a-table-column title="能力">
            <template #cell="{ record }">
              <div class="kb-capabilities" data-testid="kb-capabilities">
                <a-tag
                  v-for="item in capabilityItems(record)"
                  :key="item.key"
                  :color="item.enabled ? item.color : 'gray'"
                  :class="{ 'kb-capability-disabled': !item.enabled }"
                >
                  {{ item.label }}
                </a-tag>
              </div>
            </template>
          </a-table-column>
          <a-table-column title="操作">
            <template #cell="{ record }">
              <a-space>
                <a-button size="mini" :type="record.is_pinned ? 'primary' : 'outline'" @click="togglePin(record)">
                  <span class="sr-only">{{ record.is_pinned ? "pin-filled" : "pin" }}</span>
                  {{ record.is_pinned ? "取消置顶" : "置顶" }}
                </a-button>
                <a-button size="mini" @click="router.push(`/knowledge-bases/${record.id}`)">
                  详情
                </a-button>
                <a-button size="mini" type="primary" @click="router.push(`/knowledge-bases/${record.id}/documents`)">
                  文档管理
                </a-button>
                <a-button size="mini" @click="router.push(`/knowledge-bases/${record.id}/faqs`)">
                  FAQ
                </a-button>
                <a-button size="mini" data-testid="edit-kb-config" @click="openEditModal(record)">
                  编辑配置
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
        <a-form-item label="知识库类型">
          <a-radio-group v-model="createForm.kb_type" type="button">
            <a-radio value="document">文档知识库</a-radio>
            <a-radio value="faq">FAQ 知识库</a-radio>
          </a-radio-group>
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
        <a-form-item label="VectorStore">
          <a-tag color="blue">VectorStore：默认 Qdrant</a-tag>
        </a-form-item>
        <a-divider>索引策略</a-divider>
        <div class="form-grid form-grid--compact">
          <a-form-item label="vector">
            <a-tag color="green">vector 固定开启</a-tag>
          </a-form-item>
          <a-form-item label="keyword">
            <a-tag color="green">keyword 固定开启</a-tag>
          </a-form-item>
          <a-form-item label="parent-child">
            <a-tag color="green">parent-child 固定开启 · v0.9 固定启用</a-tag>
          </a-form-item>
          <a-form-item label="rerank">
            <a-tag color="green">rerank 固定开启 · v0.9 固定启用</a-tag>
          </a-form-item>
          <a-form-item label="Wiki">
            <a-tag color="gray">Wiki 关闭</a-tag>
          </a-form-item>
          <a-form-item label="Knowledge Graph">
            <a-tag color="gray">Knowledge Graph 关闭</a-tag>
          </a-form-item>
        </div>
        <a-divider>切分配置：只读展示</a-divider>
        <div class="form-grid form-grid--compact">
          <a-form-item label="策略">
            <a-tag>auto</a-tag>
          </a-form-item>
          <a-form-item label="chunk size">
            <a-tag>512</a-tag>
          </a-form-item>
          <a-form-item label="overlap">
            <a-tag>80</a-tag>
          </a-form-item>
          <a-form-item label="separators">
            <a-tag>"\n\n", "\n", "。"</a-tag>
          </a-form-item>
          <a-form-item label="token limit">
            <a-tag>0</a-tag>
          </a-form-item>
          <a-form-item label="languages">
            <a-tag>未指定</a-tag>
          </a-form-item>
          <a-form-item label="parent-child">
            <a-tag color="green">true</a-tag>
          </a-form-item>
          <a-form-item label="parent size">
            <a-tag>4096</a-tag>
          </a-form-item>
          <a-form-item label="child size">
            <a-tag>384</a-tag>
          </a-form-item>
        </div>
        <a-alert type="info" content="创建 payload 将按 v0.9 主链路写入固定 chunking_config 与 parser_engine_rules。" />
      </div>
    </a-modal>

    <a-modal v-model:visible="editVisible" title="编辑知识库配置" :confirm-loading="editing" @ok="submitEdit">
      <div class="modal-form">
        <a-form-item label="名称">
          <a-input v-model="editForm.name" />
        </a-form-item>
        <a-form-item label="描述">
          <a-textarea v-model="editForm.description" :auto-size="{ minRows: 3, maxRows: 5 }" />
        </a-form-item>
        <a-form-item label="知识库类型">
          <a-radio-group v-model="editForm.kb_type" type="button">
            <a-radio value="document">文档知识库</a-radio>
            <a-radio value="faq">FAQ 知识库</a-radio>
          </a-radio-group>
        </a-form-item>
        <a-form-item label="Embedding 模型">
          <a-select v-model="editForm.embedding_model_id">
            <a-option v-for="model in modelStore.embeddingModels" :key="model.id" :value="model.id">
              {{ model.name }} · {{ model.model_name }}
            </a-option>
          </a-select>
        </a-form-item>
        <a-form-item label="QA 模型">
          <a-select v-model="editForm.summary_model_id">
            <a-option v-for="model in modelStore.chatModels" :key="model.id" :value="model.id">
              {{ model.name }} · {{ model.model_name }}
            </a-option>
          </a-select>
        </a-form-item>
        <a-form-item label="VectorStore">
          <a-tag color="blue">VectorStore：默认 Qdrant</a-tag>
        </a-form-item>
        <a-divider>索引策略</a-divider>
        <div class="form-grid form-grid--compact">
          <a-form-item label="vector">
            <a-tag color="green">vector 固定开启</a-tag>
          </a-form-item>
          <a-form-item label="keyword">
            <a-tag color="green">keyword 固定开启</a-tag>
          </a-form-item>
          <a-form-item label="parent-child">
            <a-tag color="green">parent-child 固定开启 · v0.9 固定启用</a-tag>
          </a-form-item>
          <a-form-item label="rerank">
            <a-tag color="green">rerank 固定开启 · v0.9 固定启用</a-tag>
          </a-form-item>
          <a-form-item label="Wiki">
            <a-tag color="gray">Wiki 关闭</a-tag>
          </a-form-item>
          <a-form-item label="Knowledge Graph">
            <a-tag color="gray">Knowledge Graph 关闭</a-tag>
          </a-form-item>
        </div>
      </div>
    </a-modal>
  </main>
</template>
