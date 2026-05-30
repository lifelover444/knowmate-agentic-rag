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
const form = reactive({
  question: "",
  answer: "",
  metadataText: "{}",
  enabled: true,
});

function openCreate() {
  editing.value = null;
  form.question = "";
  form.answer = "";
  form.metadataText = "{}";
  form.enabled = true;
  modalVisible.value = true;
}

function openEdit(record: FAQEntryRead) {
  editing.value = record;
  form.question = record.question;
  form.answer = record.answer;
  form.metadataText = JSON.stringify(record.metadata || {}, null, 2);
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

onMounted(() => {
  Promise.all([kbStore.loadKnowledgeBase(kbId.value), kbStore.loadFaqs(kbId.value)]).catch((error) => {
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
          <a-button type="primary" @click="openCreate">新增 FAQ</a-button>
        </a-space>
      </template>
    </a-page-header>

    <section class="content-card">
      <a-table :data="kbStore.faqs" :pagination="false" row-key="id">
        <template #columns>
          <a-table-column title="问题" data-index="question" />
          <a-table-column title="答案" data-index="answer" />
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
        <a-form-item label="metadata"><a-textarea v-model="form.metadataText" :auto-size="{ minRows: 3, maxRows: 6 }" /></a-form-item>
        <a-form-item label="启用"><a-switch v-model="form.enabled" /></a-form-item>
      </div>
    </a-modal>
  </main>
</template>
