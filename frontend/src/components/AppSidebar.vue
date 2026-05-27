<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { getRootJson } from "../utils/api";

const router = useRouter();
const route = useRoute();
const healthText = ref("检查中");
const healthOk = ref(false);

const selectedKeys = computed(() => {
  if (route.path.startsWith("/knowledge-bases")) return ["/knowledge-bases"];
  if (route.path.startsWith("/settings/models")) return ["/settings/models"];
  if (route.path.startsWith("/settings/retrieval")) return ["/settings/retrieval"];
  return ["/chat"];
});

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

onMounted(loadHealth);
</script>

<template>
  <aside class="app-sidebar">
    <div class="brand">
      <span class="brand__mark">知</span>
      <div>
        <strong>knowmate 知友</strong>
        <small>知识库问答工作台</small>
      </div>
    </div>
    <a-menu class="sidebar-menu" :selected-keys="selectedKeys" @menu-item-click="navigate">
      <a-menu-item key="/chat">快速问答</a-menu-item>
      <a-menu-item key="/knowledge-bases">知识库</a-menu-item>
      <a-menu-item key="/settings/models">模型配置</a-menu-item>
      <a-menu-item key="/settings/retrieval">检索配置</a-menu-item>
    </a-menu>
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
  border-right: 1px solid var(--km-border);
  padding: 18px 12px;
  background: var(--km-bg-sidebar);
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 8px 18px;
}

.brand__mark {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border-radius: 8px;
  color: #ffffff;
  background: var(--km-primary);
  font-weight: 800;
}

.brand div {
  display: grid;
  gap: 2px;
}

.brand strong {
  color: var(--km-text-primary);
  font-size: 15px;
}

.brand small {
  color: var(--km-text-secondary);
  font-size: 12px;
}

.sidebar-menu {
  flex: 1;
  border-right: 0;
}

.sidebar-health {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 12px 8px 0;
  border: 1px solid var(--km-border);
  border-radius: 999px;
  padding: 8px 10px;
  color: var(--km-text-secondary);
  font-size: 12px;
  background: var(--km-bg-page);
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
