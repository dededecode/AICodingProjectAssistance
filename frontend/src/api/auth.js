import http from "./http";

export function getCaptcha() {
  return http.get("/auth/captcha/");
}

export function getRsaPublicKey() {
  return http.get("/auth/rsa-public-key/");
}

export function login(data) {
  return http.post("/auth/login/", data);
}

export function getMe() {
  return http.get("/auth/me/");
}

export function changePassword(data) {
  return http.post("/auth/change-password/", data);
}

// 用户管理（管理员）
export function adminListUsers(params = {}) {
  return http.get("/auth/admin-users/", { params });
}
export function adminCreateUser(data) {
  return http.post("/auth/admin-users/", data);
}
export function adminUpdateUser(id, data) {
  return http.patch(`/auth/admin-users/${id}/`, data);
}
export function adminDeleteUser(id) {
  return http.delete(`/auth/admin-users/${id}/`);
}
export function adminResetPassword(id, newPassword) {
  return http.post(`/auth/admin-users/${id}/reset-password/`, { new_password: newPassword });
}
export function adminRegenerateToken(id) {
  return http.post(`/auth/admin-users/${id}/regenerate-token/`);
}
