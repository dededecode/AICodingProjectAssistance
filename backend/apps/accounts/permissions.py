"""项目级数据访问控制权限。

规则：管理员（role=admin / 超级用户）可访问任意项目；
其他用户必须是目标项目的成员（或项目负责人）才能访问该项目相关接口。
用于所有接口的全局校验，MCP 通过用户 mcp_token 认证后同样受此约束。
"""
from rest_framework import permissions


def user_can_access_project(user, project):
    """判断用户是否有权访问项目（管理员 / 项目负责人 / 项目成员）。"""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.role == "admin":
        return True
    if project.owner_id == user.id:
        return True
    return project.member_links.filter(user=user).exists()


def _project_of(obj):
    """从模型对象解析所属项目（兼容常见外键模式）。"""
    if obj is None:
        return None
    project = getattr(obj, "project", None)
    if project is not None:
        return project
    test_case = getattr(obj, "test_case", None)
    if test_case is not None:
        return getattr(test_case, "project", None)
    return None


class IsProjectMemberOrAdmin(permissions.BasePermission):
    """项目成员或管理员权限：项目相关接口仅成员/负责人/管理员可访问。"""

    message = "无权访问该项目（仅项目成员或管理员可操作）"

    def _is_admin(self, user):
        return bool(user and (user.is_superuser or user.role == "admin"))

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if self._is_admin(user):
            return True
        # RBAC 全接口白名单：按路径映射权限组资源码，未勾选即 403（菜单与接口同码联动）
        from apps.rbac.api_map import check_api_access

        ok, code = check_api_access(user, request.path, request.method)
        if not ok:
            self.message = f"无权访问该接口（需权限组资源：{code or '未映射'}）"
            return False
        # 从查询参数或请求体中解析 project_id（对象级校验交给 has_object_permission）
        project_id = request.query_params.get("project_id")
        if not project_id:
            data = getattr(request, "data", None)
            if data is not None:
                try:
                    project_id = data.get("project_id")
                except Exception:
                    project_id = None
        if not project_id:
            return True  # 非项目作用域或按对象操作，由对象级权限兜底
        from apps.projects.models import Project

        try:
            project = Project.objects.get(id=project_id)
        except (Project.DoesNotExist, ValueError, TypeError):
            return False
        return user_can_access_project(user, project)

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if self._is_admin(user):
            return True
        project = _project_of(obj)
        if project is None:
            return True  # 无法确定项目时不拦截（对象无项目归属）
        return user_can_access_project(user, project)
