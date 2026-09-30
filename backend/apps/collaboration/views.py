from datetime import date, datetime, timedelta

from django.contrib.auth import get_user_model
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.project_planning.models import PlanTask
from apps.projects.models import Project
from services import llm
from .models import WeeklySummary, WorkGroup, WorkGroupMember, WorkGroupMessage, WorkLog
from .serializers import WeeklySummarySerializer, WorkGroupMessageSerializer, WorkGroupSerializer, WorkLogSerializer

User = get_user_model()

# ── 默认开发工作群预置文案 ──
DEFAULT_WORKFLOW_DESC = """【工作流程】
1. 项目负责人发布开发任务（任务与测试用例/测试任务由平台页面统一生成、指派），开发 agent 按任务开始提示词执行开发（参照需求文档、架构设计、原型图/UI图）。
2. 开发完成后，开发 agent 必须在群内输出总结：『我已完成xx模块功能，请测试人员基于相关任务和测试用例，开始测试该部分』。
3. 测试 agent 收到通知后，按测试任务开始提示词执行测试（拉取测试任务与用例、逐项执行、记录结果）。
4. 测试完成后在群内输出测试总结（通过率、缺陷清单）；发现缺陷由开发修复后重新提测。
5. 全部任务开发并通过测试后，项目进入验收交付。"""

DEFAULT_DEV_TASK_PROMPT = """你是本项目的全栈开发工程师，请立即开始执行分配给你的开发任务：
1. 调用 task_query（按 project_id 与自己的 user_id）获取你的任务列表与详情，明确任务模块、描述与关联的原型图/UI图（ui_images 字段）。
2. 用 prototype_image_download 拉取任务关联的 UI 图查看页面设计；用 requirement_content_query 读取需求文档，architecture_query / sql_query 读取架构与数据库设计。
3. 严格按 UI 图与架构规范完成该模块的前后端功能开发与自测。
4. 在工作群输出总结：『我已完成【模块名】模块功能，请测试人员基于相关任务和测试用例，开始测试该部分』。
5. 调用 task_update 将任务状态更新为 done。
（注意：测试用例与测试任务由平台页面统一生成并指派，你无需创建。）"""

DEFAULT_TEST_TASK_PROMPT = """你是本项目的测试工程师，开发人员已在群内通知开发完成，请立即开始测试：
1. 调用 test_task_query 获取测试任务与关联测试用例，明确本次测试范围。
2. 按测试用例逐项执行，对照原型图/UI图核对页面表现，记录每条用例的执行结果。
3. 发现缺陷时调用 bug_create 记录缺陷（注明复现步骤、期望与实际结果）。
4. 测试完成后调用 test_task_update 更新测试任务状态，并在工作群输出测试总结：『测试完成，通过 X 条、失败 Y 条，缺陷清单：…，请开发人员修复缺陷』。"""

SUMMARIZE_SYSTEM = """你是项目协作助理。请根据给定的工作群聊天记录进行总结，输出 markdown，包含两部分：

## 一、项目历程
按时间线梳理关键事件与进展：谁、在什么时间、做了什么（开发完成、测试结果、缺陷修复、重要决策等），体现项目的推进过程与当前状态。

## 二、改进建议
结合聊天记录中暴露的问题，从协作流程、开发与测试衔接、沟通效率、任务管理等角度，提出具体可执行的改进建议（3-6 条）。

只输出以上两部分 markdown 内容，不要输出其他解释。"""


class WorkLogViewSet(viewsets.ModelViewSet):
    queryset = WorkLog.objects.select_related("project", "user").all()
    serializer_class = WorkLogSerializer

    def get_queryset(self):
        qs = self.queryset
        user = self.request.user
        project_id = self.request.query_params.get("project_id")
        user_id = self.request.query_params.get("user_id")
        start = self.request.query_params.get("start")
        end = self.request.query_params.get("end")
        # 普通成员只能看自己的；管理员/负责人看全部
        if not (user.is_superuser or user.role in ("admin", "manager")):
            qs = qs.filter(user_id=user.id)
        if project_id:
            qs = qs.filter(project_id=project_id)
        if user_id:
            qs = qs.filter(user_id=user_id)
        if start:
            qs = qs.filter(date__gte=start)
        if end:
            qs = qs.filter(date__lte=end)
        return qs

    def create(self, request, *args, **kwargs):
        # 支持指定 user_id 代录工时（仅管理员/负责人/服务令牌），否则登记到当前用户
        mutable = request.data.copy()
        user_id = mutable.get("user_id")
        if user_id and (request.user.is_superuser or request.user.role in ("admin", "manager")):
            mutable["user"] = user_id
        mutable.pop("user_id", None)
        serializer = self.get_serializer(data=mutable)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def _can_manage(self, log):
        u = self.request.user
        return u.is_superuser or u.role in ("admin", "manager") or log.user_id == u.id

    def update(self, request, *args, **kwargs):
        log = self.get_object()
        if not self._can_manage(log):
            return Response({"detail": "只能修改自己的工时记录"}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        log = self.get_object()
        if not self._can_manage(log):
            return Response({"detail": "只能修改自己的工时记录"}, status=status.HTTP_403_FORBIDDEN)
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        log = self.get_object()
        if not self._can_manage(log):
            return Response({"detail": "只能删除自己的工时记录"}, status=status.HTTP_403_FORBIDDEN)
        self.perform_destroy(log)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"], url_path="statistics")
    def statistics(self, request):
        project_id = request.query_params.get("project_id")
        start = request.query_params.get("start")
        end = request.query_params.get("end")
        qs = self.get_queryset()
        if start:
            qs = qs.filter(date__gte=start)
        if end:
            qs = qs.filter(date__lte=end)

        by_project = qs.values("project_id", "project__name").annotate(total=Sum("hours"))
        by_user = qs.values("user_id", "user__username").annotate(total=Sum("hours"))
        # 总工时（用于返回 date 无关的统计）
        total = qs.aggregate(total=Sum("hours"))["total"] or 0
        return Response(
            {
                "total_hours": float(total),
                "by_project": [{"project_id": r["project_id"], "name": r["project__name"], "hours": float(r["total"])} for r in by_project],
                "by_user": [{"user_id": r["user_id"], "username": r["user__username"], "hours": float(r["total"])} for r in by_user],
            }
        )

    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request):
        """导出工时 Excel：按项目 + 日期范围。"""
        project_id = request.query_params.get("project_id")
        start = request.query_params.get("start")
        end = request.query_params.get("end")
        if not project_id:
            return Response({"detail": "缺少 project_id"}, status=status.HTTP_400_BAD_REQUEST)
        qs = self.get_queryset().filter(project_id=project_id).prefetch_related("tasks").order_by("date", "user__username")
        if start:
            qs = qs.filter(date__gte=start)
        if end:
            qs = qs.filter(date__lte=end)

        from io import BytesIO

        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.title = "工时"
        ws.append(["日期", "成员", "项目", "工时(h)", "关联任务", "工作内容"])
        for log in qs:
            ws.append(
                [
                    str(log.date),
                    log.user.username,
                    log.project.name,
                    float(log.hours),
                    "、".join(t.title for t in log.tasks.all()),
                    log.description,
                ]
            )

        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)
        response = HttpResponse(
            buf.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        filename = f"worklogs_{project_id}_{date.today()}.xlsx"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    @action(detail=False, methods=["get"], url_path="dashboard")
    def dashboard(self, request):
        """首页统计：我的周/月工时 + 团队成员周/月工时。"""
        today = timezone.localdate()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)

        def _hours(qs):
            return float(qs.aggregate(total=Sum("hours"))["total"] or 0)

        my_week = _hours(WorkLog.objects.filter(user=request.user, date__gte=week_start))
        my_month = _hours(WorkLog.objects.filter(user=request.user, date__gte=month_start))

        week_rows = (
            WorkLog.objects.filter(date__gte=week_start)
            .values("user_id", "user__username")
            .annotate(hours=Sum("hours"))
        )
        month_rows = (
            WorkLog.objects.filter(date__gte=month_start)
            .values("user_id", "user__username")
            .annotate(hours=Sum("hours"))
        )

        return Response(
            {
                "my": {"week_hours": my_week, "month_hours": my_month, "week_start": str(week_start), "month_start": str(month_start)},
                "team_week": [{"user_id": r["user_id"], "username": r["user__username"], "hours": float(r["hours"])} for r in week_rows],
                "team_month": [{"user_id": r["user_id"], "username": r["user__username"], "hours": float(r["hours"])} for r in month_rows],
            }
        )


class WeeklySummaryViewSet(viewsets.ModelViewSet):
    queryset = WeeklySummary.objects.select_related("project", "user").all()
    serializer_class = WeeklySummarySerializer

    def get_queryset(self):
        qs = self.queryset
        user = self.request.user
        project_id = self.request.query_params.get("project_id")
        if not (user.is_superuser or user.role in ("admin", "manager")):
            qs = qs.filter(user_id=user.id)
        if project_id:
            qs = qs.filter(project_id=project_id)
        return qs

    @action(detail=False, methods=["post"], url_path="generate")
    def generate(self, request):
        """AI 生成本周总结：以项目全量任务清单为上下文，对照本周工时记录，
        重点回答「本周完成了哪些任务、下周计划完成哪些任务」，限 300 字以内。"""
        project_id = request.data.get("project_id")
        week_start = request.data.get("week_start")
        if not project_id or not week_start:
            return Response({"detail": "缺少 project_id 或 week_start"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            return Response({"detail": "项目不存在"}, status=status.HTTP_404_NOT_FOUND)
        try:
            start = datetime.strptime(str(week_start), "%Y-%m-%d").date()
        except ValueError:
            return Response({"detail": "week_start 格式应为 YYYY-MM-DD"}, status=status.HTTP_400_BAD_REQUEST)
        end = start + timedelta(days=6)

        logs = WorkLog.objects.filter(project=project, date__gte=start, date__lte=end).order_by("date")
        tasks = list(
            PlanTask.objects.filter(project=project)
            .select_related("assignee")
            .order_by("sort_order", "id")
        )
        if not logs.exists() and not tasks:
            return Response(
                {"detail": "该周暂无工时记录，且项目尚无任务清单，无法生成总结"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 本周有工时登记的任务（用于让模型区分「实际动工」与「仅计划」）
        week_task_ids = set(
            PlanTask.objects.filter(work_logs__in=logs).values_list("id", flat=True)
        ) if logs.exists() else set()

        status_map = dict(PlanTask.STATUS_CHOICES)
        log_lines = [
            f"{l.date} {l.user.username}（{l.hours}h）：{l.description or '（无描述）'}" for l in logs
        ]
        task_lines = []
        for t in tasks:
            assignee = t.assignee.username if t.assignee else "未指派"
            dates = f"{t.start_date or '?'} ~ {t.end_date or '?'}"
            mark = "；本周有工时登记" if t.id in week_task_ids else ""
            task_lines.append(
                f"- [{status_map.get(t.status, t.status)}] {t.title}"
                f"（负责人：{assignee}；计划：{dates}；模块：{t.module or '-'}{mark}）"
            )

        messages = [
            {
                "role": "system",
                "content": (
                    "你是一名项目周总结助手。请基于【本周工时记录】与【项目全量任务清单】生成中文周总结，"
                    "重点回答两个问题：\n"
                    "1) 对照任务清单，本周实际完成了哪些任务（只列清单中真实存在的任务名，可依据状态与工时登记判断）；\n"
                    "2) 下周计划完成哪些任务（从清单中未完成任务里，按计划日期与优先级合理排布）。\n"
                    "硬性要求：全篇不超过 300 字；结构为【本周完成】【下周计划】两节，分点列出，"
                    "每点一句话；无重大风险则不写风险；严禁编造清单中不存在的任务，禁止套话与背景介绍。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"项目「{project.name}」本周（{start} ~ {end}）。\n\n"
                    + "【本周工时记录】\n"
                    + ("\n".join(log_lines) if log_lines else "（本周暂无工时登记）")
                    + "\n\n【项目全量任务清单】\n"
                    + "\n".join(task_lines)
                ),
            },
        ]
        try:
            content = llm.chat(messages, temperature=0.4, max_tokens=800)
        except Exception as e:
            return Response({"detail": f"AI 总结失败：{e}"}, status=status.HTTP_502_BAD_GATEWAY)

        return Response(
            {"content": content, "week_start": str(start), "log_count": logs.count(), "task_count": len(tasks)}
        )


class WorkGroupViewSet(viewsets.ModelViewSet):
    """工作群：多 agent 协作群聊（当前由用户手动切换身份发言模拟 agent）。"""

    queryset = WorkGroup.objects.select_related("project", "created_by").all()
    serializer_class = WorkGroupSerializer
    http_method_names = ["get", "post", "patch", "delete"]

    def get_queryset(self):
        user = self.request.user
        # 必须克隆：类属性 queryset 直接返回会命中 _result_cache，导致 admin 永远看到首次请求的旧列表
        qs = self.queryset.all()
        project_id = self.request.query_params.get("project_id")
        if project_id:
            qs = qs.filter(project_id=project_id)
        if user.is_superuser or user.role in ("admin", "manager"):
            return qs
        # 项目成员（含负责人）可见该项目所有群，避免"创建后看不到"
        project_ids = Project.objects.filter(
            Q(member_links__user=user) | Q(owner=user)
        ).values_list("id", flat=True)
        return qs.filter(Q(project_id__in=project_ids) | Q(members__user=user)).distinct()

    def destroy(self, request, *args, **kwargs):
        group = self.get_object()
        user = request.user
        if group.status == "dismissed":
            # 已解散的群仅 admin 可彻底删除（清理历史）
            if not self._is_admin(user):
                return Response({"detail": "仅管理员可彻底删除已解散的群"}, status=status.HTTP_403_FORBIDDEN)
        elif not (user.is_superuser or user.role in ("admin", "manager") or group.created_by_id == user.id):
            return Response({"detail": "仅创建者或管理员可删除工作群"}, status=status.HTTP_403_FORBIDDEN)
        self.perform_destroy(group)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _can_manage(self, group):
        u = self.request.user
        return u.is_superuser or u.role in ("admin", "manager") or group.created_by_id == u.id

    def _is_admin(self, user):
        return bool(user and (user.is_superuser or user.role == "admin"))

    def update(self, request, *args, **kwargs):
        if self.get_object().status == "dismissed":
            return Response({"detail": "该群已解散，不可编辑"}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="dismiss")
    def dismiss(self, request, pk=None):
        """解散工作群（仅 admin）：保留群与历史消息，禁止后续发言/编辑/成员变更。"""
        group = self.get_object()
        if not self._is_admin(request.user):
            return Response({"detail": "仅管理员可解散工作群"}, status=status.HTTP_403_FORBIDDEN)
        if group.status == "dismissed":
            return Response({"detail": "该群已解散"}, status=status.HTTP_400_BAD_REQUEST)
        group.status = "dismissed"
        group.save(update_fields=["status"])
        return Response(WorkGroupSerializer(group).data)

    @action(detail=False, methods=["post"], url_path="create-default")
    def create_default(self, request):
        """一键创建默认开发工作群（预置工作流程与开发/测试提示词），项目成员全部入群。"""
        project_id = request.data.get("project_id")
        if not project_id:
            return Response({"detail": "缺少 project_id"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            return Response({"detail": "项目不存在"}, status=status.HTTP_404_NOT_FOUND)
        name = "开发工作群"
        existed = WorkGroup.objects.filter(project=project, name=name).first()
        if existed:
            return Response(WorkGroupSerializer(existed).data)
        group = WorkGroup.objects.create(
            project=project,
            name=name,
            workflow_desc=DEFAULT_WORKFLOW_DESC,
            dev_task_prompt=DEFAULT_DEV_TASK_PROMPT,
            test_task_prompt=DEFAULT_TEST_TASK_PROMPT,
            created_by=request.user if request.user.is_authenticated else None,
        )
        # 项目所有成员（含负责人）+ 创建者入群
        user_ids = set(project.member_links.values_list("user_id", flat=True))
        if project.owner_id:
            user_ids.add(project.owner_id)
        if request.user.is_authenticated:
            user_ids.add(request.user.id)
        WorkGroupMember.objects.bulk_create(
            [WorkGroupMember(group=group, user_id=uid) for uid in user_ids if uid], ignore_conflicts=True
        )
        return Response(WorkGroupSerializer(group).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="add-member")
    def add_member(self, request, pk=None):
        group = self.get_object()
        if group.status == "dismissed":
            return Response({"detail": "该群已解散，无法变更成员"}, status=status.HTTP_403_FORBIDDEN)
        if not self._can_manage(group):
            return Response({"detail": "仅创建者或管理员可管理成员"}, status=status.HTTP_403_FORBIDDEN)
        user_id = request.data.get("user_id")
        if not user_id:
            return Response({"detail": "缺少 user_id"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            User.objects.get(id=user_id)
        except (User.DoesNotExist, ValueError, TypeError):
            return Response({"detail": "用户不存在"}, status=status.HTTP_404_NOT_FOUND)
        WorkGroupMember.objects.get_or_create(group=group, user_id=user_id)
        return Response(WorkGroupSerializer(group).data)

    @action(detail=True, methods=["post"], url_path="remove-member")
    def remove_member(self, request, pk=None):
        group = self.get_object()
        if not self._can_manage(group):
            return Response({"detail": "仅创建者或管理员可管理成员"}, status=status.HTTP_403_FORBIDDEN)
        WorkGroupMember.objects.filter(group=group, user_id=request.data.get("user_id")).delete()
        return Response(WorkGroupSerializer(group).data)

    @action(detail=True, methods=["get"], url_path="messages")
    def messages(self, request, pk=None):
        """消息列表（默认最近 200 条，按时间正序返回）。"""
        group = self.get_object()
        try:
            limit = int(request.query_params.get("limit", 200))
        except ValueError:
            limit = 200
        qs = group.messages.select_related("sender")
        if limit > 0:
            data = list(reversed(list(qs.order_by("-created_at")[:limit])))
        else:
            data = list(qs.order_by("created_at"))
        return Response(WorkGroupMessageSerializer(data, many=True).data)

    @action(detail=True, methods=["post"], url_path="send-message")
    def send_message(self, request, pk=None):
        """发消息；sender_id 用于手动切换身份模拟 agent 发言（须为群成员）。"""
        group = self.get_object()
        if group.status == "dismissed":
            return Response({"detail": "该群已解散，无法发送消息"}, status=status.HTTP_403_FORBIDDEN)
        content = (request.data.get("content") or "").strip()
        if not content:
            return Response({"detail": "消息内容不能为空"}, status=status.HTTP_400_BAD_REQUEST)
        sender_id = request.data.get("sender_id")
        if sender_id:
            try:
                sender = User.objects.get(id=sender_id)
            except (User.DoesNotExist, ValueError, TypeError):
                return Response({"detail": "发送身份用户不存在"}, status=status.HTTP_404_NOT_FOUND)
            if not group.members.filter(user=sender).exists():
                return Response({"detail": "发送身份必须是群成员"}, status=status.HTTP_400_BAD_REQUEST)
        else:
            sender = request.user
            # 当前用户（项目成员）首次发言自动入群
            if request.user.is_authenticated and not group.members.filter(user=sender).exists():
                WorkGroupMember.objects.create(group=group, user=sender)
        msg = WorkGroupMessage.objects.create(group=group, sender=sender, content=content)
        return Response(WorkGroupMessageSerializer(msg).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="summarize")
    def summarize(self, request, pk=None):
        """AI 总结群内容：项目历程 + 改进建议。"""
        group = self.get_object()
        total = group.messages.count()
        if not total:
            return Response({"detail": "群内暂无消息，无法总结"}, status=status.HTTP_400_BAD_REQUEST)
        # 取最近 200 条，按时间正序拼接
        lines = [
            f"[{timezone.localtime(m.created_at):%m-%d %H:%M}] {m.sender.username}: {m.content}"
            for m in list(group.messages.select_related("sender").order_by("-created_at")[:200])[::-1]
        ]
        chat_text = "\n".join(lines)[:30000]
        messages = [
            {"role": "system", "content": SUMMARIZE_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"工作群「{group.name}」（项目：{group.project.name}）聊天记录"
                    f"（共 {total} 条，以下为最近 {len(lines)} 条）：\n\n{chat_text}"
                ),
            },
        ]
        try:
            content = llm.chat(messages, temperature=0.3)
        except Exception as e:
            return Response({"detail": f"AI 总结失败：{e}"}, status=status.HTTP_502_BAD_GATEWAY)
        return Response({"content": content, "message_count": total})
