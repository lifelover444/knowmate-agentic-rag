import { createRouter, createWebHashHistory } from "vue-router";
import type { RouteRecordRaw } from "vue-router";

export const routes: RouteRecordRaw[] = [
  { path: "/", redirect: "/chat" },
  { path: "/chat", component: () => import("../views/ChatView.vue"), meta: { title: "快速问答" } },
  { path: "/knowledge-bases", component: () => import("../views/KnowledgeBaseView.vue"), meta: { title: "知识库" } },
  {
    path: "/knowledge-bases/:kbId",
    component: () => import("../views/KnowledgeBaseDetailView.vue"),
    meta: { title: "知识库详情" },
  },
  {
    path: "/knowledge-bases/:kbId/documents",
    component: () => import("../views/DocumentsView.vue"),
    meta: { title: "文档管理" },
  },
  {
    path: "/knowledge-bases/:kbId/faqs",
    component: () => import("../views/FAQView.vue"),
    meta: { title: "FAQ 管理" },
  },
  { path: "/settings", component: () => import("../views/SettingsView.vue"), meta: { title: "设置中心" } },
  { path: "/settings/models", redirect: { path: "/settings", query: { section: "models" } } },
  {
    path: "/settings/vector-stores",
    redirect: { path: "/settings", query: { section: "vector-stores" } },
  },
  {
    path: "/settings/retrieval",
    redirect: { path: "/settings", query: { section: "retrieval" } },
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
