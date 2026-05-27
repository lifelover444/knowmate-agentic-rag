import { createRouter, createWebHashHistory } from "vue-router";
import type { RouteRecordRaw } from "vue-router";

export const routes: RouteRecordRaw[] = [
  { path: "/", redirect: "/chat" },
  { path: "/chat", component: () => import("../views/ChatView.vue"), meta: { title: "快速问答" } },
  { path: "/knowledge-bases", component: () => import("../views/KnowledgeBaseView.vue"), meta: { title: "知识库" } },
  {
    path: "/knowledge-bases/:kbId/documents",
    component: () => import("../views/DocumentsView.vue"),
    meta: { title: "文档管理" },
  },
  { path: "/settings/models", component: () => import("../views/ModelSettingsView.vue"), meta: { title: "模型配置" } },
  {
    path: "/settings/retrieval",
    component: () => import("../views/RetrievalSettingsView.vue"),
    meta: { title: "检索配置" },
  },
];

const router = createRouter({
  history: createWebHashHistory(),
  routes,
});

router.afterEach((to) => {
  document.title = `${String(to.meta.title || "工作台")} - knowmate 知友`;
});

export default router;
