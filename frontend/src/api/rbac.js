import http from "./http";

// 当前用户资源：enabled=全局已启用码，allowed=本人拥有码
export function myResources() {
  return http.get("/rbac/my-resources/");
}
// 角色管理（管理员）
export function listRoles() {
  return http.get("/rbac/roles/");
}
export function createRole(name) {
  return http.post("/rbac/roles/create/", { name });
}
export function deleteRole(id) {
  return http.delete(`/rbac/roles/${id}/delete/`);
}
export function saveRoleResources(id, codes) {
  return http.put(`/rbac/roles/${id}/resources/`, { codes });
}
