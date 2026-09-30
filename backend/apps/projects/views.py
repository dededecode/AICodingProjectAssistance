from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.utils import timezone as dj_timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.rbac.permissions import ApiResourcePermission
from .models import Project, ProjectMember
from .serializers import MemberInviteSerializer, ProjectSerializer

User = get_user_model()


class IsOwnerOrAdmin(permissions.BasePermission):
    """仅项目负责人或管理员可操作。"""

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_superuser or user.role == "admin":
            return True
        return obj.owner_id == user.id


class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.select_related("owner").all()
    serializer_class = ProjectSerializer

    def get_permissions(self):
        perms = [permissions.IsAuthenticated(), ApiResourcePermission()]
        if self.action in ("update", "partial_update", "destroy"):
            perms.append(IsOwnerOrAdmin())
        return perms

    def get_queryset(self):
        user = self.request.user
        qs = self.queryset
        if not (user.is_superuser or user.role == "admin"):
            # 普通用户只看自己负责或参与的
            qs = qs.filter(owner_id=user.id) | qs.filter(member_links__user_id=user.id)
        return qs.distinct()

    @action(detail=True, methods=["post"], url_path="members/invite")
    def invite(self, request, pk=None):
        project = self.get_object()
        if not (
            request.user.is_superuser
            or request.user.role == "admin"
            or project.owner_id == request.user.id
            or project.member_links.filter(user=request.user, role="manager").exists()
        ):
            return Response({"detail": "无权限操作该项目成员"}, status=status.HTTP_403_FORBIDDEN)

        serializer = MemberInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_id = serializer.validated_data["user_id"]
        role = serializer.validated_data["role"]

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"detail": "用户不存在"}, status=status.HTTP_404_NOT_FOUND)

        _, created = ProjectMember.objects.get_or_create(
            project=project, user=user, defaults={"role": role}
        )
        if not created:
            return Response({"detail": "该用户已是项目成员"}, status=status.HTTP_400_BAD_REQUEST)

        return Response(ProjectSerializer(project, context={"request": request}).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path="members/(?P<user_id>[0-9]+)")
    def remove_member(self, request, pk=None, user_id=None):
        project = self.get_object()
        if not (
            request.user.is_superuser
            or request.user.role == "admin"
            or project.owner_id == request.user.id
            or project.member_links.filter(user=request.user, role="manager").exists()
        ):
            return Response({"detail": "无权限操作该项目成员"}, status=status.HTTP_403_FORBIDDEN)
        if int(user_id) == project.owner_id:
            return Response({"detail": "不能移除项目负责人"}, status=status.HTTP_400_BAD_REQUEST)

        deleted, _ = ProjectMember.objects.filter(project=project, user_id=user_id).delete()
        if not deleted:
            return Response({"detail": "该用户不是项目成员"}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"], url_path="member-profiles")
    def member_profiles(self, request, pk=None):
        """项目成员画像：项目内角色 + 能力描述 + 承担任务统计。

        权限：仅项目负责人(owner)、项目内项目经理(manager)或管理员可查；
        普通成员不可查看。供页面或 MCP（AI 分配权重/派单）使用。
        """
        from django.db.models import Count, Q, Sum

        from apps.project_planning.models import PlanTask

        project = self.get_object()
        user = request.user
        can_view = (
            user.is_superuser
            or user.role == "admin"
            or project.owner_id == user.id
            or project.member_links.filter(user=user, role="manager").exists()
        )
        if not can_view:
            return Response(
                {"detail": "仅项目经理或管理员可查看成员画像"},
                status=status.HTTP_403_FORBIDDEN,
            )

        links = list(project.member_links.select_related("user").order_by("id"))
        stats_map = {}
        if links:
            agg = (
                PlanTask.objects.filter(project=project)
                .values("assignee_id")
                .annotate(
                    total=Count("id"),
                    pending=Count("id", filter=Q(status="pending")),
                    executing=Count("id", filter=Q(status="executing")),
                    done=Count("id", filter=Q(status="done")),
                    blocked=Count("id", filter=Q(status="blocked")),
                    est_days=Sum("estimated_days"),
                )
            )
            stats_map = {r["assignee_id"]: r for r in agg}
        profiles = []
        for link in links:
            u = link.user
            s = stats_map.get(u.id) or {}
            profiles.append(
                {
                    "user_id": u.id,
                    "username": u.username,
                    "name": u.name or "",
                    "role": link.role,
                    "role_display": link.get_role_display(),
                    "capability": u.capability or "",
                    "joined_at": dj_timezone.localtime(link.joined_at).strftime("%Y-%m-%d") if link.joined_at else "",
                    "task_stats": {
                        "total": s.get("total") or 0,
                        "pending": s.get("pending") or 0,
                        "executing": s.get("executing") or 0,
                        "done": s.get("done") or 0,
                        "blocked": s.get("blocked") or 0,
                        "estimated_days": float(s.get("est_days") or 0),
                    },
                }
            )
        return Response(profiles)
