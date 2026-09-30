import axios from "axios";
import { ElMessage } from "element-plus";

const http = axios.create({
  baseURL: "/api",
  timeout: 30000,
});

// 请求拦截：自动附加 JWT
http.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 响应拦截：统一错误提示
http.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const detail = error.response?.data?.detail;
    const msg = detail || error.message || "请求失败";
    if (status === 401) {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      localStorage.removeItem("user");
      if (!window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
    } else {
      ElMessage.error(msg);
    }
    return Promise.reject(error);
  }
);

export default http;
