import http from "./http";

export function listBugs(params = {}) {
  return http.get("/bugs/", { params });
}
export function createBug(data) {
  return http.post("/bugs/", data);
}
export function updateBug(id, data) {
  return http.patch(`/bugs/${id}/`, data);
}
export function deleteBug(id) {
  return http.delete(`/bugs/${id}/`);
}
export function bugStatistics(projectId) {
  return http.get("/bugs/statistics/", { params: { project_id: projectId } });
}
export function bugFromTestTask(data) {
  return http.post("/bugs/from-test-task/", data);
}
export function uploadBugImage(id, formData) {
  return http.post(`/bugs/${id}/upload-image/`, formData);
}
export function deleteBugImage(id, imageId) {
  return http.post(`/bugs/${id}/delete-image/`, { image_id: imageId });
}
