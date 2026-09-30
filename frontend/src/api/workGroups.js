import http from "./http";

export function listWorkGroups(params = {}) {
  return http.get("/work-groups/", { params });
}

export function createWorkGroup(data) {
  return http.post("/work-groups/", data);
}

export function updateWorkGroup(id, data) {
  return http.patch(`/work-groups/${id}/`, data);
}

export function deleteWorkGroup(id) {
  return http.delete(`/work-groups/${id}/`);
}

export function dismissWorkGroup(id) {
  return http.post(`/work-groups/${id}/dismiss/`);
}

export function createDefaultWorkGroup(projectId) {
  return http.post("/work-groups/create-default/", { project_id: projectId });
}

export function addWorkGroupMember(id, userId) {
  return http.post(`/work-groups/${id}/add-member/`, { user_id: userId });
}

export function removeWorkGroupMember(id, userId) {
  return http.post(`/work-groups/${id}/remove-member/`, { user_id: userId });
}

export function listGroupMessages(id, limit = 200) {
  return http.get(`/work-groups/${id}/messages/`, { params: { limit } });
}

export function sendGroupMessage(id, data) {
  return http.post(`/work-groups/${id}/send-message/`, data);
}

export function summarizeWorkGroup(id) {
  return http.post(`/work-groups/${id}/summarize/`, {}, { timeout: 600000 });
}
