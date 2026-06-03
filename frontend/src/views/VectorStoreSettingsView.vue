<script setup lang="ts">
import { Message } from "@arco-design/web-vue";
import { onMounted, reactive, ref } from "vue";
import { useVectorStoresStore } from "../stores/vectorStores";
import { formatApiError } from "../utils/api";

const store = useVectorStoresStore();
const saving = ref(false);
const form = reactive({
  name: "默认 Qdrant",
  host: "localhost",
  port: 6333,
  api_key: "",
  use_tls: false,
  is_default: true,
});

function payload() {
  return {
    name: form.name,
    provider: "qdrant",
    status: "active",
    is_default: form.is_default,
    config_json: {
      host: form.host,
      port: Number(form.port) || 6333,
      api_key: form.api_key || undefined,
      use_tls: form.use_tls,
    },
  };
}

async function save() {
  saving.value = true;
  try {
    await store.createVectorStore(payload());
    form.api_key = "";
    Message.success("VectorStore 已保存");
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  } finally {
    saving.value = false;
  }
}

async function testConnection() {
  try {
    const result = await store.testVectorStore({ provider: "qdrant", config_json: payload().config_json });
    result.ok ? Message.success(result.message) : Message.error(result.message);
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

async function makeDefault(id: string) {
  try {
    await store.updateVectorStore(id, { provider: "qdrant", config_json: {}, is_default: true });
    Message.success("已设为默认 VectorStore");
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

async function remove(id: string) {
  try {
    await store.deleteVectorStore(id);
    Message.success("VectorStore 已删除");
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

function typeStatusText(status: string): string {
  if (status === "available") return "可用";
  if (status === "planned") return "planned";
  return "unavailable";
}

function typeStatusColor(status: string): string {
  if (status === "available") return "green";
  if (status === "planned") return "orange";
  return "gray";
}

onMounted(() => {
  Promise.all([store.loadVectorStores(), store.loadVectorStoreTypes()]).catch((error) => {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  });
});
</script>

<template>
  <main class="page-shell">
    <a-page-header title="VectorStore 管理" subtitle="管理知识库可绑定的 Qdrant VectorStore，敏感配置不会明文回显。" />

    <section class="content-card">
      <div class="section-heading">
        <div>
          <h2>VectorStore Types</h2>
          <p>当前仅 Qdrant 可用，OpenSearch、Elasticsearch、Milvus、Weaviate、Doris、Tencent VectorDB 为 planned。</p>
        </div>
      </div>
      <div class="vector-type-grid">
        <article v-for="item in store.vectorStoreTypes" :key="item.type" class="vector-type-card">
          <header>
            <strong>{{ item.label }}</strong>
            <a-tag :color="typeStatusColor(item.status)">{{ typeStatusText(item.status) }}</a-tag>
          </header>
          <p>{{ item.description }}</p>
          <div class="vector-field-list">
            <span>connection_fields</span>
            <a-tag v-for="field in item.connection_fields" :key="`${item.type}-conn-${field.name}`">
              {{ field.label }}{{ field.sensitive ? " · sensitive" : "" }}
            </a-tag>
          </div>
          <div class="vector-field-list">
            <span>index_fields</span>
            <a-tag v-for="field in item.index_fields" :key="`${item.type}-index-${field.name}`">
              {{ field.label }}
            </a-tag>
          </div>
        </article>
      </div>
    </section>

    <section class="content-card">
      <div class="section-heading">
        <div>
          <h2>新增 Qdrant</h2>
          <p>v0.5 仅注册 Qdrant provider，后续可通过 registry 接入更多向量库。</p>
        </div>
        <a-space>
          <a-button :loading="store.testing" @click="testConnection">测试连接</a-button>
          <a-button type="primary" :loading="saving" @click="save">保存</a-button>
        </a-space>
      </div>
      <div class="form-grid">
        <a-form-item label="名称"><a-input v-model="form.name" /></a-form-item>
        <a-form-item label="Host"><a-input v-model="form.host" /></a-form-item>
        <a-form-item label="Port"><a-input-number v-model="form.port" /></a-form-item>
        <a-form-item label="API Key"><a-input-password v-model="form.api_key" placeholder="保存后不回显明文" /></a-form-item>
        <a-form-item label="TLS"><a-switch v-model="form.use_tls" /></a-form-item>
        <a-form-item label="设为默认"><a-switch v-model="form.is_default" /></a-form-item>
      </div>
    </section>

    <section class="content-card">
      <a-table :data="store.vectorStores" :loading="store.loading" :pagination="false" row-key="id">
        <template #columns>
          <a-table-column title="名称" data-index="name" />
          <a-table-column title="Provider" data-index="provider" />
          <a-table-column title="状态" data-index="status" />
          <a-table-column title="默认">
            <template #cell="{ record }">
              <a-tag :color="record.is_default ? 'green' : 'gray'">{{ record.is_default ? "默认" : "非默认" }}</a-tag>
            </template>
          </a-table-column>
          <a-table-column title="配置">
            <template #cell="{ record }">
              <code>{{ record.config_json }}</code>
            </template>
          </a-table-column>
          <a-table-column title="操作">
            <template #cell="{ record }">
              <a-space>
                <a-button size="mini" :disabled="record.is_default" @click="makeDefault(record.id)">设为默认</a-button>
                <a-popconfirm content="确认删除这个 VectorStore？" @ok="remove(record.id)">
                  <a-button size="mini" status="danger" :disabled="record.is_default">删除</a-button>
                </a-popconfirm>
              </a-space>
            </template>
          </a-table-column>
        </template>
      </a-table>
    </section>
  </main>
</template>

<style scoped>
.vector-type-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}

.vector-type-card {
  display: grid;
  gap: 8px;
  border: 1px solid var(--km-border);
  border-radius: var(--km-radius);
  padding: 12px;
  background: var(--km-bg-card);
}

.vector-type-card header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.vector-type-card p {
  margin: 0;
  color: var(--km-text-secondary);
  font-size: 12px;
  line-height: 1.6;
}

.vector-field-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}

.vector-field-list span {
  width: 100%;
  color: var(--km-text-secondary);
  font-size: 12px;
}
</style>
