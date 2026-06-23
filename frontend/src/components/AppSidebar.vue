<script setup lang="ts">
import { Message } from "@arco-design/web-vue";
import { IconDelete, IconEdit } from "@arco-design/web-vue/es/icon";
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useChatStore } from "../stores/chat";
import type { ChatSessionRead } from "../types/api";
import { formatApiError, getRootJson } from "../utils/api";

const router = useRouter();
const route = useRoute();
const chat = useChatStore();
const healthText = ref("检查中");
const healthOk = ref(false);
const historyCollapsed = ref(false);
const renameVisible = ref(false);
const renameTitle = ref("");
const renamingSessionId = ref("");

const selectedKeys = computed(() => {
  if (route.path.startsWith("/knowledge-bases")) return ["/knowledge-bases"];
  if (route.path.startsWith("/settings")) return ["/settings"];
  return ["/chat"];
});
const isChatRoute = computed(() => route.path.startsWith("/chat"));
const recentSessions = computed(() => chat.filteredSessions.slice(0, 8));

async function loadHealth() {
  try {
    await getRootJson("/health");
    healthOk.value = true;
    healthText.value = "后端已连接";
  } catch {
    healthOk.value = false;
    healthText.value = "后端未连接";
  }
}

function navigate(key: string) {
  router.push(key);
}

async function newConversation() {
  chat.currentSession = null;
  chat.messages = [];
  router.push("/chat");
}

async function openSession(sessionId: string) {
  await chat.loadSession(sessionId);
  router.push("/chat");
}

function openRename(session: ChatSessionRead) {
  renamingSessionId.value = session.id;
  renameTitle.value = session.title;
  renameVisible.value = true;
}

async function submitRename() {
  try {
    await chat.renameSession(renamingSessionId.value, renameTitle.value);
    renameVisible.value = false;
    Message.success("会话名称已更新。");
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

async function deleteSession(session: ChatSessionRead) {
  try {
    await chat.deleteSession(session.id);
    Message.success("会话已删除。");
  } catch (error) {
    Message.error(formatApiError(error instanceof Error ? error.message : error));
  }
}

onMounted(() => {
  loadHealth();
  chat.loadSessions().catch(() => undefined);
});
</script>

<template>
  <aside class="app-sidebar">
    <div class="brand">
      <span class="brand__mark"></span>
      <strong>knowmate知友</strong>
    </div>
    <nav class="sidebar-nav">
      <button type="button" :class="{ active: selectedKeys[0] === '/chat' }" @click="newConversation">
        <span class="nav-icon nav-icon--chat"></span>
        <span>新对话</span>
      </button>
      <button type="button" :class="{ active: selectedKeys[0] === '/knowledge-bases' }" @click="navigate('/knowledge-bases')">
        <span class="nav-icon nav-icon--book"></span>
        <span>知识库</span>
      </button>
      <button type="button" :class="{ active: false }" @click="navigate('/chat')">
        <span class="nav-icon nav-icon--search"></span>
        <span>搜索</span>
      </button>
      <button type="button" :class="{ active: selectedKeys[0] === '/settings' }" @click="navigate('/settings')">
        <span class="nav-icon nav-icon--plug"></span>
        <span>设置</span>
      </button>
    </nav>

    <section v-if="isChatRoute" class="sidebar-history">
      <button type="button" class="history-title" @click="historyCollapsed = !historyCollapsed">
        <span>历史对话</span>
        <span>{{ historyCollapsed ? "⌄" : "⌃" }}</span>
      </button>
      <div v-show="!historyCollapsed" class="history-list">
        <div
          v-for="session in recentSessions"
          :key="session.id"
          class="history-item"
          :class="{ active: chat.currentSession?.id === session.id }"
        >
          <button class="history-item__content" type="button" @click="openSession(session.id)">
            <span>{{ session.title }}</span>
            <small v-if="session.is_pinned">置顶</small>
          </button>
          <div class="history-item__actions">
            <a-button
              size="mini"
              shape="circle"
              title="重命名会话"
              aria-label="重命名会话"
              @click.stop="openRename(session)"
            >
              <template #icon><IconEdit /></template>
            </a-button>
            <a-popconfirm content="确认删除这个会话？" @ok="deleteSession(session)">
              <a-button
                size="mini"
                shape="circle"
                status="danger"
                title="删除会话"
                aria-label="删除会话"
                @click.stop
              >
                <template #icon><IconDelete /></template>
              </a-button>
            </a-popconfirm>
          </div>
        </div>
      </div>
    </section>

    <div class="sidebar-spacer"></div>
    <div class="sidebar-health" :class="{ healthy: healthOk }">
      <span class="sidebar-health__dot"></span>
      <span>{{ healthText }}</span>
    </div>
  </aside>

  <a-modal v-model:visible="renameVisible" title="重命名会话" :on-before-ok="submitRename">
    <a-input v-model="renameTitle" placeholder="请输入会话名称" />
  </a-modal>
</template>

<style scoped>
.app-sidebar {
  display: flex;
  flex-direction: column;
  width: var(--km-sidebar-width);
  height: 100vh;
  border-right: 1px solid #e7e9ec;
  padding: 30px 16px 14px;
  background: #f4f5f7;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 4px 10px 34px;
}

.brand__mark {
  position: relative;
  display: block;
  width: 31px;
  height: 31px;
  border-radius: 5px 18px 18px 18px;
  background: linear-gradient(135deg, #33d680 0%, #11c46f 100%);
}

.brand__mark::before,
.brand__mark::after {
  position: absolute;
  background: #f4f5f7;
  content: "";
}

.brand__mark::before {
  top: -4px;
  left: 9px;
  width: 8px;
  height: 35px;
  border-radius: 8px;
  transform: rotate(-38deg);
}

.brand__mark::after {
  right: -2px;
  bottom: 8px;
  width: 28px;
  height: 8px;
  border-radius: 8px;
  transform: rotate(-12deg);
}

.brand strong {
  color: #586174;
  font-size: 22px;
  font-weight: 600;
}

.sidebar-nav {
  display: grid;
  gap: 18px;
  padding: 0 8px;
}

.sidebar-nav button {
  display: flex;
  align-items: center;
  gap: 14px;
  width: 100%;
  border: 0;
  border-radius: 12px;
  padding: 6px 6px;
  color: #282d33;
  background: transparent;
  font-size: 18px;
  text-align: left;
  cursor: pointer;
}

.sidebar-nav button:hover,
.sidebar-nav button.active {
  background: rgba(255, 255, 255, 0.55);
}

.nav-icon {
  position: relative;
  display: inline-grid;
  width: 24px;
  height: 24px;
  flex: 0 0 24px;
  place-items: center;
  color: currentColor;
}

.nav-icon--chat {
  border: 2px solid currentColor;
  border-radius: 6px;
}

.nav-icon--chat::after {
  position: absolute;
  bottom: -5px;
  left: 5px;
  width: 8px;
  height: 8px;
  border-bottom: 2px solid currentColor;
  border-left: 2px solid currentColor;
  background: #f4f5f7;
  transform: rotate(-45deg);
  content: "";
}

.nav-icon--book {
  border: 2px solid currentColor;
  border-radius: 6px;
}

.nav-icon--book::before {
  width: 2px;
  height: 18px;
  background: currentColor;
  content: "";
}

.nav-icon--search {
  border: 2px solid currentColor;
  border-radius: 999px;
}

.nav-icon--search::after {
  position: absolute;
  right: -5px;
  bottom: -3px;
  width: 10px;
  height: 2px;
  border-radius: 2px;
  background: currentColor;
  transform: rotate(45deg);
  content: "";
}

.nav-icon--plug::before,
.nav-icon--plug::after {
  position: absolute;
  background: currentColor;
  content: "";
}

.nav-icon--plug::before {
  width: 20px;
  height: 4px;
  border-radius: 6px;
  transform: rotate(-38deg);
}

.nav-icon--plug::after {
  width: 9px;
  height: 9px;
  border: 2px solid currentColor;
  border-radius: 999px;
  background: transparent;
  transform: translate(5px, -6px);
}

.sidebar-history {
  display: grid;
  gap: 12px;
  margin-top: 46px;
  min-height: 0;
  padding: 0 0 0 6px;
}

.history-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border: 0;
  padding: 0 10px;
  color: #8a929e;
  background: transparent;
  font-size: 16px;
  cursor: pointer;
}

.history-list {
  display: grid;
  gap: 8px;
  max-height: calc(100vh - 430px);
  overflow: auto;
  padding-right: 4px;
}

.history-item {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  width: 100%;
  border: 0;
  border-radius: 14px;
  padding: 8px 8px 8px 14px;
  color: #23282f;
  background: transparent;
}

.history-item__content {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  min-width: 0;
  border: 0;
  padding: 2px 0;
  color: inherit;
  background: transparent;
  font-size: 17px;
  text-align: left;
  cursor: pointer;
}

.history-item:hover,
.history-item.active,
.history-item:focus-within {
  background: #e9e9ea;
}

.history-item__content span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-item__content small {
  color: #8a929e;
  font-size: 12px;
}

.history-item__actions {
  display: flex;
  align-items: center;
  gap: 4px;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.16s ease;
}

.history-item:hover .history-item__actions,
.history-item.active .history-item__actions,
.history-item:focus-within .history-item__actions {
  opacity: 1;
  pointer-events: auto;
}

.history-item__actions :deep(.arco-btn) {
  color: #667085;
  background: rgba(255, 255, 255, 0.4);
}

.history-item__actions :deep(.arco-btn:hover) {
  background: #ffffff;
}

.sidebar-spacer {
  flex: 1;
}

.sidebar-health {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 12px 4px;
  border: 1px solid #e0e3e8;
  border-radius: 999px;
  padding: 8px 10px;
  color: var(--km-text-secondary);
  font-size: 12px;
  background: rgba(255, 255, 255, 0.72);
}

.sidebar-health__dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: var(--km-error);
}

.sidebar-health.healthy .sidebar-health__dot {
  background: var(--km-success);
}

</style>
