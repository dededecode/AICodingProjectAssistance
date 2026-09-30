import http from "./http";

export function listProjects() {
  return http.get("/projects/");
}

export function createProject(data) {
  return http.post("/projects/", data);
}

export function getProject(id) {
  return http.get(`/projects/${id}/`);
}

export function updateProject(id, data) {
  return http.patch(`/projects/${id}/`, data);
}

export function deleteProject(id) {
  return http.delete(`/projects/${id}/`);
}

export function inviteMember(projectId, data) {
  return http.post(`/projects/${projectId}/members/invite/`, data);
}

export function removeMember(projectId, userId) {
  return http.delete(`/projects/${projectId}/members/${userId}/`);
}

export function listUsers(search = "") {
  return http.get("/auth/users/", { params: { search } });
}
