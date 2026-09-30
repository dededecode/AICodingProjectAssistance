import http from "./http";

export function listTasks(params = {}) {
  return http.get("/plan-tasks/", { params });
}

export function createTask(data) {
  return http.post("/plan-tasks/", data);
}

export function updateTask(id, data) {
  return http.patch(`/plan-tasks/${id}/`, data);
}

export function deleteTask(id) {
  return http.delete(`/plan-tasks/${id}/`);
}

export function exportTasks(params) {
  return http.get("/plan-tasks/export/", { params, responseType: "blob" });
}
