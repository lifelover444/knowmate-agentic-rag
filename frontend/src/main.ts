import { createApp } from "vue";
import ArcoVue from "@arco-design/web-vue";
import "@arco-design/web-vue/dist/arco.css";
import "highlight.js/styles/github.css";
import { createPinia } from "pinia";
import router from "./router";
import App from "./App.vue";
import "./styles/app.css";

createApp(App)
  .use(ArcoVue)
  .use(createPinia())
  .use(router)
  .mount("#app");
