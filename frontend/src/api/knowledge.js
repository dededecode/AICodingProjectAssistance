import http from "./http";

export function listKnowledge(projectId) {
  return http.get("/knowledge/", { params: { project_id: projectId } });
}

export function getAllKnowledge(projectId) {
  return http.get("/knowledge/all/", { params: { project_id: projectId } });
}

export function deleteKnowledgeItem(id) {
  return http.delete(`/knowledge/${id}/`);
}

export function clearKnowledge(projectId) {
  // 清空项目知识库（向量 + 条目），仅管理员/负责人/项目经理
  return http.post("/knowledge/clear/", { project_id: projectId });
}

export function searchKnowledge(data) {
  return http.post("/knowledge/search/", data);
}

export function addKnowledge(data) {
  return http.post("/knowledge/add/", data);
}

export function qaKnowledge(data) {
  return http.post("/knowledge/qa/", data, { timeout: 120000 });
}

export function ingestKnowledge(data) {
  // AI 整理某环节文档并写入知识库
  return http.post("/knowledge/ingest/", data, { timeout: 120000 });
}
