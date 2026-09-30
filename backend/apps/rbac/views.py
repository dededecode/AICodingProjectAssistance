from django.contrib.auth.models import Group
from django.db import transaction
from rest_framework import permissions, status, views
from rest_framework.response import Response

from .models import BUILTIN_ROLES, RoleResource


def _is_admin(user):
    return bool(user and (user.is_superuser or user.role == "admin"))


class RoleListView(views.APIView):
    """角色列表（= Django Group）+ 每个角色已配置的资源码。仅管理员。"""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not _is_admin(request.user):
            return Response({"detail": "仅管理员可管理角色"}, status=status.HTTP_403_FORBIDDEN)
        roles = []
        for g in Group.objects.all().order_by("id"):
            codes = list(
                RoleResource.objects.filter(group=g).values_list("code", flat=True)
            )
            roles.append(
                {
                    "id": g.id,
                    "name": g.name,
                    "builtin": g.name in BUILTIN_ROLES,
                    "codes": codes,
                }
            )
        return Response(roles)


class RoleCreateView(views.APIView):
    """新建角色（Group）。仅管理员。"""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if not _is_admin(request.user):
            return Response({"detail": "仅管理员可管理角色"}, status=status.HTTP_403_FORBIDDEN)
        name = (request.data.get("name") or "").strip()
        if not name:
            return Response({"detail": "角色名称不能为空"}, status=status.HTTP_400_BAD_REQUEST)
        if Group.objects.filter(name=name).exists():
            return Response({"detail": "角色已存在"}, status=status.HTTP_400_BAD_REQUEST)
        g = Group.objects.create(name=name)
        return Response({"id": g.id, "name": g.name, "builtin": False, "codes": []}, status=status.HTTP_201_CREATED)


class RoleResourceSaveView(views.APIView):
    """全量保存某角色的资源码配置（覆盖式）。仅管理员。"""

    permission_classes = [permissions.IsAuthenticated]

    def put(self, request, pk):
        if not _is_admin(request.user):
            return Response({"detail": "仅管理员可管理角色"}, status=status.HTTP_403_FORBIDDEN)
        try:
            group = Group.objects.get(id=pk)
        except Group.DoesNotExist:
            return Response({"detail": "角色不存在"}, status=status.HTTP_404_NOT_FOUND)

        codes = request.data.get("codes") or []
        if not isinstance(codes, list):
            return Response({"detail": "codes 必须是数组"}, status=status.HTTP_400_BAD_REQUEST)

        code_type = {}
        for c in codes:
            prefix = c.split(":", 1)[0] if ":" in c else "menu"
            code_type[c] = prefix if prefix in ("menu", "btn", "api") else "menu"

        RoleResource.objects.filter(group=group).delete()
        with transaction.atomic():
            RoleResource.objects.bulk_create(
                [
                    RoleResource(group=group, code=c, resource_type=code_type[c])
                    for c in dict.fromkeys(codes)
                ]
            )
        return Response({"id": group.id, "name": group.name, "codes": list(dict.fromkeys(codes))})


class RoleDeleteView(views.APIView):
    """删除自定义角色。内置角色不可删。仅管理员。"""

    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, pk):
        if not _is_admin(request.user):
            return Response({"detail": "仅管理员可管理角色"}, status=status.HTTP_403_FORBIDDEN)
        try:
            group = Group.objects.get(id=pk)
        except Group.DoesNotExist:
            return Response({"detail": "角色不存在"}, status=status.HTTP_404_NOT_FOUND)
        if group.name in BUILTIN_ROLES:
            return Response({"detail": "内置角色不可删除"}, status=status.HTTP_400_BAD_REQUEST)
        group.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MyResourcesView(views.APIView):
    """当前用户资源码集合：enabled=全局已启用码，allowed=本人拥有码。登录用户即可。

    前端 hasPerm(code) = !enabled.includes(code) || allowed.includes(code)
    （未启用的码放行，启用后按 allowed 判定）
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from .services import user_allowed_codes

        # allowed：本人分组勾选拥有的资源码（叠加层只增不减，未勾选走前端 defaultRoles 兜底）
        return Response({"allowed": sorted(user_allowed_codes(request.user))})
