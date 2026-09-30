import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    host: "127.0.0.1",
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        timeout: 600000,
        proxyTimeout: 600000,
      },
      "/media": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
