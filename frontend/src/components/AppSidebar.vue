<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useChatStore } from "../stores/chat";
import { getRootJson } from "../utils/api";

const router = useRouter();
const route = useRoute();
const chat = useChatStore();
const healthText = ref("检查中");
const healthOk = ref(false);
const historyCollapsed = ref(false);

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
        <button
          v-for="session in recentSessions"
          :key="session.id"
          type="button"
          :class="{ active: chat.currentSession?.id === session.id }"
          @click="openSession(session.id)"
        >
          <span>{{ session.title }}</span>
          <small v-if="session.is_pinned">置顶</small>
        </button>
      </div>
    </section>

    <div class="sidebar-spacer"></div>
    <div class="sidebar-health" :class="{ healthy: healthOk }">
      <span class="sidebar-health__dot"></span>
      <span>{{ healthText }}</span>
    </div>
  </aside>
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

.history-list button {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  width: 100%;
  border: 0;
  border-radius: 14px;
  padding: 10px 14px;
  color: #23282f;
  background: transparent;
  font-size: 17px;
  text-align: left;
  cursor: pointer;
}

.history-list button:hover,
.history-list button.active {
  background: #e9e9ea;
}

.history-list span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-list small {
  color: #8a929e;
  font-size: 12px;
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
