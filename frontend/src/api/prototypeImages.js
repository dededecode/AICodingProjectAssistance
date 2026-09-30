import http from "./http";

// 原型图 / UI 图
export function listPrototypeImages(projectId, params = {}) {
  return http.get("/prototype-images/", { params: { project_id: projectId, ...params } });
}
export function uploadPrototypeImage(formData) {
  return http.post("/prototype-images/", formData);
}
export function deletePrototypeImage(id) {
  return http.delete(`/prototype-images/${id}/`);
}
export function batchDeletePrototypeImages(projectId, ids) {
  return http.post("/prototype-images/batch-delete/", { ids }, { params: { project_id: projectId } });
}
export function updatePrototypeImage(id, data) {
  return http.patch(`/prototype-images/${id}/`, data);
}
