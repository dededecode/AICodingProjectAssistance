import http from "./http";

export function listRequirements(projectId) {
  return http.get("/requirements/", { params: { project_id: projectId } });
}

export function uploadRequirement(formData) {
  // 图文上传含 AI 取名，耗时较长，单独放宽超时到 5 分钟
  return http.post("/requirements/upload/", formData, { timeout: 300000 });
}

export function analyzeRequirement(id) {
  // AI 分析耗时较长，单独放宽超时到 10 分钟
  return http.post(`/requirements/${id}/analyze/`, null, { timeout: 600000 });
}

export function confirmRequirement(id) {
  return http.post(`/requirements/${id}/confirm/`);
}

export function deleteRequirement(id) {
  return http.delete(`/requirements/${id}/`);
}
