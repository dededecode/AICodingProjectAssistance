import http from "./http";

export function listWikiSources(projectId) {
  return http.get("/wiki/sources/", { params: { project_id: projectId } });
}

export function listWikiPages(projectId, params = {}) {
  return http.get("/wiki/", { params: { project_id: projectId, ...params } });
}

export function getWikiPage(id) {
  return http.get(`/wiki/${id}/`);
}

export function deleteWikiPage(id) {
  return http.delete(`/wiki/${id}/`);
}

export function compileWiki(data) {
  // 异步触发编译：立即返回 log_id，后台线程执行，通过 getCompileStatus 轮询结果
  return http.post("/wiki/compile/", data, { timeout: 30000 });
}

export function getCompileStatus(projectId) {
  // 轮询编译进度（running/success/failed）
  return http.get("/wiki/compile-status/", { params: { project_id: projectId } });
}

export function cancelWikiCompile(data) {
  // 取消进行中的编译任务（running 日志标记为失败）
  return http.post("/wiki/compile-cancel/", data);
}

export function searchWiki(data) {
  return http.post("/wiki/search/", data);
}

export function clearWiki(projectId) {
  // 清空项目 Wiki（页面 + 向量），仅管理员/负责人/项目经理
  return http.post("/wiki/clear/", { project_id: projectId });
}
