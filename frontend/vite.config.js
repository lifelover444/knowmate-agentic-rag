import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";

const backendTarget = process.env.VITE_API_PROXY_TARGET || "http://127.0.0.1:8000";
const apiProxy = {
  target: backendTarget,
  changeOrigin: true,
};

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      "/api": apiProxy,
      "/health": apiProxy,
    },
  },
  preview: {
    proxy: {
      "/api": apiProxy,
      "/health": apiProxy,
    },
  },
});
