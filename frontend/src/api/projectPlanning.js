import http from "./http";

export function listProjectPlans(projectId) {
  return http.get("/project-plans/", { params: { project_id: projectId } });
}

export function generateProjectPlan(data) {
  // AI 生成计划较慢，放宽超时
  return http.post("/project-plans/generate/", data, { timeout: 180000 });
}

export function updateProjectPlan(id, data) {
  return http.patch(`/project-plans/${id}/`, data);
}

export function regenerateProjectPlan(id, data = {}) {
  // data.suggestion: 修改意见（可选）
  return http.post(`/project-plans/${id}/regenerate/`, data, { timeout: 180000 });
}

export function generatePlanTasks(id) {
  // AI 生成任务较慢，放宽超时到 10 分钟
  return http.post(`/project-plans/${id}/generate-tasks/`, {}, { timeout: 600000 });
}

export function deleteProjectPlan(id) {
  return http.delete(`/project-plans/${id}/`);
}
