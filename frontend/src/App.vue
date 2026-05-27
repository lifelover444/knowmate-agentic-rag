<script setup lang="ts">
import AppSidebar from "./components/AppSidebar.vue";
</script>

<template>
  <a-layout class="app-layout">
    <a-layout-sider class="app-layout__sider" :width="220">
      <AppSidebar />
    </a-layout-sider>
    <a-layout-content class="app-layout__content">
      <router-view />
    </a-layout-content>
  </a-layout>
</template>
