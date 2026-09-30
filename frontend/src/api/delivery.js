import http from "./http";

export function listDeliveryDocs(projectId, keyword = "") {
  return http.get("/delivery-docs/", { params: { project_id: projectId, keyword: keyword || undefined } });
}
export function uploadDeliveryDoc(formData) {
  return http.post("/delivery-docs/upload/", formData);
}
// 直接以内容创建（Markdown），source 记为手动上传
export function createDeliveryDoc(data) {
  return http.post("/delivery-docs/", data);
}
export function deleteDeliveryDoc(id) {
  return http.delete(`/delivery-docs/${id}/`);
}
