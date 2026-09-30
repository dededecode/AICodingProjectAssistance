import http from "./http";

export function getAiConfig() {
  return http.get("/ai-config/");
}
export function saveAiConfig(data) {
  return http.put("/ai-config/", data);
}
export function testAiConfig(kind) {
  // 本地模型首次加载/下载较慢，放宽超时
  return http.post("/ai-config/test/", { kind }, { timeout: 180000 });
}
export function getEmbeddingLogs(params) {
  return http.get("/ai-config/embedding-logs/", { params });
}
