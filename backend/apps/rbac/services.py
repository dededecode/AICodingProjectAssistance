"""RBAC 资源校验工具。

核心约定（叠加层、平滑演进、只增不减）：
  - 用户权限完全由「权限组(Group)」决定：只有用户被分配的组勾选过某资源码，该码才对用户放行(True)；
  - 否则一律返回 None，由调用方沿用原有 role 硬编码逻辑兜底（不拦截、不收窄）；
  - 管理员/超管（role=admin 或 is_superuser）始终有权，不受权限组配置限制。
  - 不再把 User.role 与同名内置组自动绑定：除 admin 外，角色的默认权限不生效，
    一切看用户管理里分配了哪些权限组。
"""

from .models import RoleResource


def user_allowed_codes(user):
    """用户被分配的所有权限组勾选拥有的资源码集合（并集）。

    注意：不包含 role 同名内置组的自动绑定——除 admin（短路）外，权限只由
    用户管理里分配的权限组决定，role 仅作为账号类型/原有硬编码权限的依据。
    """
    if not user or not user.is_authenticated:
        return set()
    return set(
        RoleResource.objects.filter(group__in=user.groups.all()).values_list("code", flat=True)
    )


def check_resource(user, code):
    """校验用户是否有某资源码权限（叠加层）。

    返回 True 表示该码被用户权限组勾选；返回 None 表示未配置（走兜底，不拦截）。
    管理员/超管始终返回 True。注意：本函数不会返回 False（不提供显式拒绝，
    收紧能力由前端 defaultRoles 与原有 role 硬编码承担）。
    """
    if not code:
        return None
    if user and (user.is_superuser or user.role == "admin"):
        return True
    if code in user_allowed_codes(user):
        return True
    return None
