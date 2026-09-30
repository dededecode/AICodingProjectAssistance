"""API 资源权限类：按权限组白名单校验接口访问（与前端菜单同码联动）。

用法：挂到显式声明 permission_classes 的视图上（全局默认类已内置同样校验）：
    permission_classes = [IsAuthenticated, ApiResourcePermission]
"""
from rest_framework import permissions

from .api_map import check_api_access


class ApiResourcePermission(permissions.BasePermission):
    message = "无权访问该接口（权限组未授权该资源）"

    def has_permission(self, request, view):
        ok, _ = check_api_access(request.user, request.path, request.method)
        return ok
