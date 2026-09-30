import http from "./http";

// 工时
export function listWorkLogs(params = {}) {
  return http.get("/work-logs/", { params });
}
export function createWorkLog(data) {
  return http.post("/work-logs/", data);
}
export function updateWorkLog(id, data) {
  return http.patch(`/work-logs/${id}/`, data);
}
export function deleteWorkLog(id) {
  return http.delete(`/work-logs/${id}/`);
}
export function workLogStatistics(params = {}) {
  return http.get("/work-logs/statistics/", { params });
}
export function workLogDashboard() {
  return http.get("/work-logs/dashboard/");
}
export function exportWorkLogs(params) {
  return http.get("/work-logs/export/", { params, responseType: "blob" });
}

// 周总结
export function listWeeklySummaries(params = {}) {
  return http.get("/weekly-summaries/", { params });
}
export function createWeeklySummary(data) {
  return http.post("/weekly-summaries/", data);
}
export function generateWeeklySummary(data) {
  // LLM 生成较慢（含全量任务清单上下文），单独放宽到 5 分钟（全局默认 30s）
  return http.post("/weekly-summaries/generate/", data, { timeout: 300000 });
}
export function deleteWeeklySummary(id) {
  return http.delete(`/weekly-summaries/${id}/`);
}
