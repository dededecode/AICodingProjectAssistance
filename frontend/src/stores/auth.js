import { defineStore } from "pinia";
import { login as apiLogin, getMe } from "../api/auth";
import { myResources } from "../api/rbac";

export const useAuthStore = defineStore("auth", {
  state: () => ({
    user: JSON.parse(localStorage.getItem("user") || "null"),
    accessToken: localStorage.getItem("access_token") || "",
    refreshToken: localStorage.getItem("refresh_token") || "",
    // RBAC 资源：allowed=本人权限组勾选拥有的资源码（白名单制，未勾选不可见）
    allowedCodes: JSON.parse(localStorage.getItem("allowed_codes") || "[]"),
  }),
  getters: {
    isAuthenticated: (state) => !!state.accessToken,
    displayName: (state) => state.user?.username || "",
  },
  actions: {
    setSession(data) {
      this.accessToken = data.access;
      this.refreshToken = data.refresh;
      this.user = data.user;
      localStorage.setItem("access_token", data.access);
      localStorage.setItem("refresh_token", data.refresh);
      localStorage.setItem("user", JSON.stringify(data.user));
    },
    async login(payload) {
      const { data } = await apiLogin(payload);
      this.setSession(data);
      return data;
    },
    async fetchMe() {
      const { data } = await getMe();
      this.user = data;
      localStorage.setItem("user", JSON.stringify(data));
    },
    async fetchResources() {
      if (!this.accessToken) return;
      try {
        const { data } = await myResources();
        this.allowedCodes = data.allowed || [];
        localStorage.setItem("allowed_codes", JSON.stringify(this.allowedCodes));
      } catch (e) {
        // 拉取失败时沿用本地缓存（未配置视为未授权，不影响登录使用）
        this.allowedCodes = JSON.parse(localStorage.getItem("allowed_codes") || "[]");
      }
    },
    logout() {
      this.user = null;
      this.accessToken = "";
      this.refreshToken = "";
      this.allowedCodes = [];
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      localStorage.removeItem("user");
      localStorage.removeItem("allowed_codes");
      localStorage.removeItem("configured_codes");
    },
  },
});
