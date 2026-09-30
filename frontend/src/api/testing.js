import http from "./http";

// 测试用例
export function listTestCases(params = {}) {
  return http.get("/test-cases/", { params });
}
export function createTestCase(data) {
  return http.post("/test-cases/", data);
}
export function updateTestCase(id, data) {
  return http.patch(`/test-cases/${id}/`, data);
}
export function deleteTestCase(id) {
  return http.delete(`/test-cases/${id}/`);
}

// 测试任务
export function listTestTasks(params = {}) {
  return http.get("/test-tasks/", { params });
}
export function dispatchTestTask(data) {
  return http.post("/test-tasks/dispatch/", data);
}
export function batchDispatchTestTask(data) {
  return http.post("/test-tasks/batch-dispatch/", data);
}
export function updateTestTask(id, data) {
  return http.patch(`/test-tasks/${id}/`, data);
}
export function deleteTestTask(id) {
  return http.delete(`/test-tasks/${id}/`);
}
export function exportTestTasks(params) {
  return http.get("/test-tasks/export/", { params, responseType: "blob" });
}
export function testStatistics(projectId) {
  return http.get("/test-tasks/statistics/", { params: { project_id: projectId } });
}

// AI 生成测试用例 / 测试报告
export function generateTestCases(data) {
  return http.post("/test-cases/generate/", data, { timeout: 120000 });
}
export function generateTestReport(data) {
  return http.post("/test-tasks/report/", data, { timeout: 120000 });
}
