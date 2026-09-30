import { defineStore } from "pinia";
import { listProjects } from "../api/projects";

// 模块级共享加载 promise：避免布局与视图同时挂载时重复请求
let loadingPromise = null;

export const useProjectStore = defineStore("project", {
  state: () => ({
    projects: [],
    // 全局当前项目：持久化，切换菜单/刷新页面后保持
    currentId: JSON.parse(localStorage.getItem("current_project_id") || "null"),
  }),
  getters: {
    current: (state) => state.projects.find((p) => p.id === state.currentId) || null,
  },
  actions: {
    // 拉取项目列表并校验当前选择（失效则回退到第一个项目）
    async ensureLoaded() {
      if (!loadingPromise) {
        loadingPromise = listProjects()
          .then(({ data }) => {
            this.projects = data;
            if (!data.some((p) => p.id === this.currentId)) {
              this.setCurrent(data.length ? data[0].id : null);
            }
          })
          .finally(() => {
            loadingPromise = null;
          });
      }
      return loadingPromise;
    },
    setCurrent(id) {
      this.currentId = id ?? null;
      localStorage.setItem("current_project_id", JSON.stringify(this.currentId));
    },
  },
});
