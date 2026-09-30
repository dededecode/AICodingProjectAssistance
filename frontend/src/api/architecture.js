import http from "./http";

export function listArchitecture(projectId) {
  return http.get("/architecture/", { params: { project_id: projectId } });
}

export function createArchitecture(data) {
  return http.post("/architecture/", data);
}

export function updateArchitecture(id, data) {
  return http.patch(`/architecture/${id}/`, data);
}

export function deleteArchitecture(id) {
  return http.delete(`/architecture/${id}/`);
}

export function getChatHistory(id) {
  return http.get(`/architecture/${id}/chat-history/`);
}

export function chatArchitecture(id, data) {
  // AI 对话较慢，放宽超时
  return http.post(`/architecture/${id}/chat/`, data, { timeout: 120000 });
}
