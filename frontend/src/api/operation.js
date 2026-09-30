import http from "./http";

// 运营记录
export function listOperationItems(params = {}) {
  return http.get("/operation-items/", { params });
}
export function createOperationItem(data) {
  return http.post("/operation-items/", data);
}
export function updateOperationItem(id, data) {
  return http.patch(`/operation-items/${id}/`, data);
}
export function deleteOperationItem(id) {
  return http.delete(`/operation-items/${id}/`);
}
export function operationStatistics(projectId) {
  return http.get("/operation-items/statistics/", { params: { project_id: projectId } });
}

// 运营指标
export function listOperationMetrics(params = {}) {
  return http.get("/operation-metrics/", { params });
}
export function createOperationMetric(data) {
  return http.post("/operation-metrics/", data);
}
export function updateOperationMetric(id, data) {
  return http.patch(`/operation-metrics/${id}/`, data);
}
export function deleteOperationMetric(id) {
  return http.delete(`/operation-metrics/${id}/`);
}
