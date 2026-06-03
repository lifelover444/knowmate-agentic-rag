<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

interface CommandItem {
  id: string;
  label: string;
  description: string;
  keywords: string;
  to: string | { path: string; query?: Record<string, string> };
}

const router = useRouter();
const route = useRoute();
const commandPaletteOpen = ref(false);
const commandPaletteQuery = ref("");

const currentKbId = computed(() => String(route.params.kbId || ""));
const commands = computed<CommandItem[]>(() => [
  { id: "chat", label: "快速问答", description: "进入 Chat / Quick Q&A", keywords: "chat qa 问答", to: "/chat" },
  {
    id: "history-search",
    label: "历史问答搜索",
    description: "进入 Chat 侧栏搜索历史回答",
    keywords: "message history search answer 历史 回答",
    to: "/chat",
  },
  { id: "kb", label: "知识库", description: "创建和管理知识库", keywords: "kb knowledge base", to: "/knowledge-bases" },
  {
    id: "documents",
    label: "文档管理",
    description: "上传、解析、查看 chunks",
    keywords: "document upload parse chunk",
    to: currentKbId.value ? `/knowledge-bases/${currentKbId.value}/documents` : "/knowledge-bases",
  },
  {
    id: "faqs",
    label: "FAQ 管理",
    description: "维护 FAQ 和相似问法",
    keywords: "faq question answer",
    to: currentKbId.value ? `/knowledge-bases/${currentKbId.value}/faqs` : "/knowledge-bases",
  },
  {
    id: "models",
    label: "模型配置",
    description: "配置 OpenAI-compatible 模型",
    keywords: "model qa embedding rerank",
    to: { path: "/settings", query: { section: "models" } },
  },
  {
    id: "retrieval",
    label: "检索设置",
    description: "调整检索、重排和 chunking",
    keywords: "retrieval search rerank chunking",
    to: { path: "/settings", query: { section: "retrieval" } },
  },
  {
    id: "parser",
    label: "解析器状态",
    description: "查看 parser_engine_status",
    keywords: "parser mineru ocr",
    to: { path: "/settings", query: { section: "parser" } },
  },
  {
    id: "storage",
    label: "存储状态",
    description: "查看 local storage 和运行状态",
    keywords: "storage qdrant system",
    to: { path: "/settings", query: { section: "storage" } },
  },
]);

const filteredCommands = computed(() => {
  const query = commandPaletteQuery.value.trim().toLowerCase();
  if (!query) return commands.value;
  return commands.value.filter((command) =>
    `${command.label} ${command.description} ${command.keywords}`.toLowerCase().includes(query),
  );
});

function openCommandPalette() {
  commandPaletteOpen.value = true;
}

function closeCommandPalette() {
  commandPaletteOpen.value = false;
  commandPaletteQuery.value = "";
}

function runCommand(command: CommandItem) {
  router.push(command.to);
  closeCommandPalette();
}

function handleShortcut(event: KeyboardEvent) {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    openCommandPalette();
  }
}

onMounted(() => window.addEventListener("keydown", handleShortcut));
onBeforeUnmount(() => window.removeEventListener("keydown", handleShortcut));
</script>

<template>
  <button type="button" class="command-button" data-testid="open-command-palette" @click="openCommandPalette">
    <span>命令</span>
    <small>Ctrl+K</small>
  </button>

  <a-modal
    v-model:visible="commandPaletteOpen"
    modal-class="command-palette"
    title="Command Palette"
    :footer="false"
    @cancel="closeCommandPalette"
  >
    <a-input
      v-model="commandPaletteQuery"
      data-testid="command-palette-query"
      placeholder="搜索命令，例如 模型、文档、检索"
      allow-clear
    />
    <div class="command-list" data-testid="command-palette">
      <button v-for="command in filteredCommands" :key="command.id" type="button" @click="runCommand(command)">
        <strong>{{ command.label }}</strong>
        <span>{{ command.description }}</span>
      </button>
      <a-empty v-if="!filteredCommands.length" description="没有匹配命令" />
    </div>
  </a-modal>
</template>

<style scoped>
.command-button {
  position: fixed;
  right: 18px;
  top: 14px;
  z-index: 20;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 1px solid var(--km-border);
  border-radius: var(--km-radius);
  padding: 7px 10px;
  color: var(--km-text-primary);
  background: var(--km-bg-card);
  box-shadow: var(--km-shadow);
  cursor: pointer;
}

.command-button small {
  color: var(--km-text-secondary);
  font-size: 12px;
}

.command-list {
  display: grid;
  gap: 8px;
  margin-top: 12px;
}

.command-list button {
  display: grid;
  gap: 4px;
  border: 1px solid var(--km-border);
  border-radius: var(--km-radius);
  padding: 10px 12px;
  color: var(--km-text-primary);
  background: var(--km-bg-card);
  text-align: left;
  cursor: pointer;
}

.command-list button:hover {
  border-color: #bfead6;
  background: var(--km-bg-deep);
}

.command-list span {
  color: var(--km-text-secondary);
  font-size: 12px;
}
</style>
