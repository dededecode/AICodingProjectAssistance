import json
import logging
import re
import time
from datetime import date, datetime

from django.db import transaction
from django.http import HttpResponse, StreamingHttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.projects.models import Project, ProjectMember
from apps.requirements.models import PrototypeImage, Requirement
from . import planning as planning_mod
from .models import PlanTask, ProjectPlan, ProjectPlanMember
from .serializers import PlanTaskSerializer, ProjectPlanGenerateSerializer, ProjectPlanSerializer

logger = logging.getLogger(__name__)

_KIND_DISPLAY = {"prototype": "原型图", "ui": "UI图", "flow": "业务流程图", "other": "其它"}


def _prototype_image_list(project) -> list:
    """项目原型图/UI图清单 [(图名, 类型)]，供生成任务时 AI 关联引用。"""
    return [
        (name, _KIND_DISPLAY.get(kind, kind))
        for name, kind in PrototypeImage.objects.filter(project=project)
        .order_by("id").values_list("name", "kind")
    ]


def _clean_ui_images(project, raw) -> list:
    """校验任务关联图名称：去重、只保留项目原型图库中真实存在的名称。"""
    if not isinstance(raw, list):
        return []
    valid = set(PrototypeImage.objects.filter(project=project).values_list("name", flat=True))
    out = []
    for n in raw:
        if isinstance(n, str) and n.strip() and n.strip() in valid and n.strip() not in out:
            out.append(n.strip())
    return out[:20]


def _sse(data):
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


class ProjectPlanViewSet(viewsets.ModelViewSet):
    queryset = ProjectPlan.objects.select_related("project", "requirement", "created_by").all()
    serializer_class = ProjectPlanSerializer
    http_method_names = ["get", "post", "patch", "delete"]

    def get_queryset(self):
        qs = self.queryset
        project_id = self.request.query_params.get("project_id")
        if project_id:
            qs = qs.filter(project_id=project_id)
        return qs

    def destroy(self, request, *args, **kwargs):
        plan = self.get_object()
        user = request.user
        if not (user.is_superuser or user.role in ("admin", "manager") or plan.created_by_id == user.id):
            return Response({"detail": "无权删除该计划"}, status=status.HTTP_403_FORBIDDEN)
        self.perform_destroy(plan)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _prepare_generate(self, request):
        """校验并准备生成计划的参数，返回 (project, requirement, data, members)。校验失败抛 DRF 异常。"""
        serializer = ProjectPlanGenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            project = Project.objects.get(id=data["project_id"])
        except Project.DoesNotExist:
            raise ValidationError("项目不存在")

        if project.status == "requirement":
            raise ValidationError("请先完成需求分析并确认入库，项目进入「项目计划」状态后再进行计划安排。")

        try:
            requirement = Requirement.objects.get(id=data["requirement_id"], project_id=project.id)
        except Requirement.DoesNotExist:
            raise ValidationError("所选需求文档不存在或不属于该项目")

        start = data["start_date"]
        launch = data["launch_date"]
        if start < date.today():
            raise ValidationError("计划开始时间不能早于今天")
        if launch < date.today():
            raise ValidationError("上线时间不能早于今天")
        if launch < start:
            raise ValidationError("计划上线时间不能早于计划开始时间")

        member_ids = [m["user_id"] for m in data["members"]]
        valid_ids = set(ProjectMember.objects.filter(project=project, user_id__in=member_ids).values_list("user_id", flat=True))
        invalid = [mid for mid in member_ids if mid not in valid_ids]
        if invalid:
            raise ValidationError(f"以下用户不是该项目成员：{invalid}")

        member_users = []
        for m in data["members"]:
            user = ProjectMember.objects.select_related("user").get(project=project, user_id=m["user_id"]).user
            member_users.append(user)
        members = [(u.username, m["weight"], (u.capability or "").strip()) for u, m in zip(member_users, data["members"])]
        return project, requirement, data, members

    def _create_plan(self, project, requirement, data, content, user):
        plan = ProjectPlan.objects.create(
            project=project,
            name=data["name"],
            requirement=requirement,
            planned_members=len(data["members"]),
            start_date=data["start_date"],
            launch_date=data["launch_date"],
            plan_content=content,
            created_by=user if user.is_authenticated else None,
        )
        for m in data["members"]:
            ProjectPlanMember.objects.create(plan=plan, user_id=m["user_id"], weight=m["weight"])
        if project.status == "planning":
            project.status = "architecture"
            project.save(update_fields=["status"])
        return plan

    @action(detail=False, methods=["post"], url_path="generate")
    def generate(self, request):
        """生成项目计划（文字总结）。支持传入 plan_content 直接保存（用于流式完成后落库）。"""
        try:
            project, requirement, data, members = self._prepare_generate(request)
        except ValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        plan_content = (request.data.get("plan_content") or "").strip()
        if plan_content:
            content = plan_content
        else:
            try:
                content = planning_mod.generate_plan(requirement, data["name"], data["start_date"], data["launch_date"], members)
            except Exception as e:
                return Response({"detail": f"AI 计划生成失败：{e}"}, status=status.HTTP_502_BAD_GATEWAY)

        plan = self._create_plan(project, requirement, data, content, request.user)
        return Response(ProjectPlanSerializer(plan).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="generate-stream")
    def generate_stream(self, request):
        """流式生成项目计划。传入 partial_content 表示「继续生成」：从上次已生成内容接着写。"""
        try:
            project, requirement, data, members = self._prepare_generate(request)
        except ValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        partial = (request.data.get("partial_content") or "").strip()

        def gen():
            try:
                yield _sse({"type": "start"})
                for piece in planning_mod.generate_plan_stream(
                    requirement,
                    data["name"],
                    data["start_date"],
                    data["launch_date"],
                    members,
                    partial_content=partial,
                ):
                    yield _sse({"type": "chunk", "content": piece})
                yield _sse({"type": "done"})
            except Exception as e:
                yield _sse({"type": "error", "message": str(e)})

        response = StreamingHttpResponse(gen(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response

    @action(detail=True, methods=["post"], url_path="regenerate")
    def regenerate(self, request, pk=None):
        """根据【修改意见】结合当前计划版本重新生成计划。"""
        plan = self.get_object()
        suggestion = (request.data.get("suggestion") or "").strip()
        if not suggestion:
            return Response({"detail": "请输入修改意见后再重新生成"}, status=status.HTTP_400_BAD_REQUEST)
        members = [(m.user.username, m.weight, (m.user.capability or "").strip()) for m in plan.members.select_related("user")]
        try:
            content = planning_mod.generate_plan(
                plan.requirement,
                plan.name,
                plan.start_date,
                plan.launch_date,
                members,
                suggestion=suggestion,
                current_content=plan.plan_content or "",
            )
        except Exception as e:
            return Response({"detail": f"AI 重新生成失败：{e}"}, status=status.HTTP_502_BAD_GATEWAY)
        plan.plan_content = content
        plan.save(update_fields=["plan_content"])
        return Response(ProjectPlanSerializer(plan).data)

    @action(detail=True, methods=["post"], url_path="regenerate-stream")
    def regenerate_stream(self, request, pk=None):
        """流式重新生成计划：按【修改意见】结合当前版本边生成边输出，支持 partial_content 继续。"""
        plan = self.get_object()
        suggestion = (request.data.get("suggestion") or "").strip()
        if not suggestion:
            return Response({"detail": "请输入修改意见后再重新生成"}, status=status.HTTP_400_BAD_REQUEST)
        partial = (request.data.get("partial_content") or "").strip()
        members = [(m.user.username, m.weight, (m.user.capability or "").strip()) for m in plan.members.select_related("user")]

        def gen():
            try:
                yield _sse({"type": "start"})
                for piece in planning_mod.generate_plan_stream(
                    plan.requirement,
                    plan.name,
                    plan.start_date,
                    plan.launch_date,
                    members,
                    partial_content=partial,
                    suggestion=suggestion,
                    current_content=plan.plan_content or "",
                ):
                    yield _sse({"type": "chunk", "content": piece})
                yield _sse({"type": "done"})
            except Exception as e:
                yield _sse({"type": "error", "message": str(e)})

        response = StreamingHttpResponse(gen(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response

    @action(detail=True, methods=["post"], url_path="generate-tasks")
    def generate_tasks(self, request, pk=None):
        """第二步：用户确认计划后，生成结构化任务并指派到人（覆盖该计划原有任务）。"""
        plan = self.get_object()
        t0 = time.time()
        logger.info("[生成任务] 收到请求：plan=%s id=%s project=%s", plan.name, plan.id, plan.project_id)
        members = [(m.user.username, m.weight) for m in plan.members.select_related("user")]
        user_map = {m.user.username: m.user.id for m in plan.members.select_related("user")}
        try:
            raw_tasks = planning_mod.generate_tasks(
                plan.requirement, plan.name, plan.start_date, plan.launch_date, members,
                plan.plan_content or "", prototype_images=_prototype_image_list(plan.project),
            )
        except Exception as e:
            logger.error("[生成任务] AI 调用异常（已耗时 %.1fs）：%s", time.time() - t0, e)
            return Response({"detail": f"AI 任务生成失败：{e}"}, status=status.HTTP_502_BAD_GATEWAY)
        logger.info("[生成任务] AI 返回 %s 条，开始写入（累计耗时 %.1fs）", len(raw_tasks), time.time() - t0)

        with transaction.atomic():
            plan.tasks.all().delete()
            created = 0
            for idx, t in enumerate(raw_tasks):
                if not isinstance(t, dict):
                    continue
                PlanTask.objects.create(
                    plan=plan,
                    project=plan.project,
                    title=str(t.get("title", "")).strip()[:300],
                    description=str(t.get("description", "") or ""),
                    module=str(t.get("module", "") or ""),
                    difficulty=_norm_difficulty(t.get("difficulty")),
                    estimated_days=float(t.get("estimated_days") or 0),
                    assignee_id=user_map.get(t.get("assignee")),
                    start_date=_parse_date(t.get("start_date")),
                    end_date=_parse_date(t.get("end_date")),
                    depends=str(t.get("depends", "") or ""),
                    ui_images=_clean_ui_images(plan.project, t.get("ui_images")),
                    sort_order=idx,
                )
                created += 1
        logger.info("[生成任务] 完成：写入 %s 条任务，总耗时 %.1fs", created, time.time() - t0)
        return Response(ProjectPlanSerializer(plan).data)

    @action(detail=True, methods=["post"], url_path="generate-tasks-stream")
    def generate_tasks_stream(self, request, pk=None):
        """流式生成任务：边生成边输出，完成后自动解析并写入任务（避免客户端超时触发重试）。"""
        plan = self.get_object()
        t0 = time.time()
        logger.info("[生成任务][流式] 收到请求：plan=%s id=%s project=%s", plan.name, plan.id, plan.project_id)
        members = [(m.user.username, m.weight) for m in plan.members.select_related("user")]
        user_map = {m.user.username: m.user.id for m in plan.members.select_related("user")}

        def gen():
            raw_parts = []
            try:
                yield _sse({"type": "start"})
                for piece in planning_mod.generate_tasks_stream(
                    plan.requirement, plan.name, plan.start_date, plan.launch_date, members,
                    plan.plan_content or "", prototype_images=_prototype_image_list(plan.project),
                ):
                    raw_parts.append(piece)
                    yield _sse({"type": "chunk", "content": piece})
                logger.info("[生成任务][流式] AI 输出完成，累计耗时 %.1fs，开始解析", time.time() - t0)
                tasks = _parse_tasks_json("".join(raw_parts))
                if not tasks:
                    raise ValueError("AI 返回内容无法解析为任务列表")
                with transaction.atomic():
                    plan.tasks.all().delete()
                    created = 0
                    for idx, t in enumerate(tasks):
                        if not isinstance(t, dict):
                            continue
                        PlanTask.objects.create(
                            plan=plan,
                            project=plan.project,
                            title=str(t.get("title", "")).strip()[:300],
                            description=str(t.get("description", "") or ""),
                            module=str(t.get("module", "") or ""),
                            difficulty=_norm_difficulty(t.get("difficulty")),
                            estimated_days=float(t.get("estimated_days") or 0),
                            assignee_id=user_map.get(t.get("assignee")),
                            start_date=_parse_date(t.get("start_date")),
                            end_date=_parse_date(t.get("end_date")),
                            depends=str(t.get("depends", "") or ""),
                            ui_images=_clean_ui_images(plan.project, t.get("ui_images")),
                            sort_order=idx,
                        )
                        created += 1
                logger.info("[生成任务][流式] 完成：写入 %s 条任务，总耗时 %.1fs", created, time.time() - t0)
                yield _sse({"type": "done", "created": created})
            except Exception as e:
                logger.error("[生成任务][流式] 失败（耗时 %.1fs）：%s", time.time() - t0, e)
                yield _sse({"type": "error", "message": str(e)})

        response = StreamingHttpResponse(gen(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response

    @action(detail=True, methods=["post"], url_path="tasks-import")
    def tasks_import(self, request, pk=None):
        """直接提交一份已生成好的任务列表并保存（不调用服务端 AI），覆盖该计划现有任务。

        tasks 每项须含非空 title；assignee 用成员用户名（须为该计划成员，否则报错便于修正）。
        供其它 agent 生成好任务 JSON 后直接入库。
        """
        plan = self.get_object()
        tasks = request.data.get("tasks")
        if not isinstance(tasks, list) or not tasks:
            return Response({"detail": "tasks 不能为空，需为任务对象数组"}, status=status.HTTP_400_BAD_REQUEST)
        user_map = {m.user.username: m.user.id for m in plan.members.select_related("user")}
        unknown = set()
        cleaned = []
        for t in tasks:
            if not isinstance(t, dict):
                return Response({"detail": "tasks 每一项都必须是对象"}, status=status.HTTP_400_BAD_REQUEST)
            if not str(t.get("title") or "").strip():
                return Response({"detail": "每条任务必须有非空 title"}, status=status.HTTP_400_BAD_REQUEST)
            assignee = str(t.get("assignee") or "").strip()
            if assignee and assignee not in user_map:
                unknown.add(assignee)
                continue
            cleaned.append(t)
        if unknown:
            return Response(
                {"detail": f"以下负责人不是该计划成员，无法指派：{sorted(unknown)}；请修正后重试"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        with transaction.atomic():
            plan.tasks.all().delete()
            created = 0
            for idx, t in enumerate(cleaned):
                try:
                    est_days = float(t.get("estimated_days") or 0)
                except (TypeError, ValueError):
                    est_days = 0
                PlanTask.objects.create(
                    plan=plan,
                    project=plan.project,
                    title=str(t.get("title", "")).strip()[:300],
                    description=str(t.get("description", "") or ""),
                    module=str(t.get("module", "") or ""),
                    difficulty=_norm_difficulty(t.get("difficulty")),
                    estimated_days=est_days,
                    assignee_id=user_map.get(str(t.get("assignee") or "").strip()),
                    start_date=_parse_date(t.get("start_date")),
                    end_date=_parse_date(t.get("end_date")),
                    depends=str(t.get("depends", "") or ""),
                    ui_images=_clean_ui_images(plan.project, t.get("ui_images")),
                    sort_order=idx,
                )
                created += 1
        return Response({"imported": created, "plan": ProjectPlanSerializer(plan).data})


def _parse_tasks_json(raw: str) -> list:
    """把 AI 输出的原始文本解析为任务列表，容错（截取首个 JSON 对象/数组）。"""
    raw = raw.strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except Exception:
        m = re.search(r"\{.*\}", raw, re.S)
        if not m:
            return []
        try:
            data = json.loads(m.group(0))
        except Exception:
            return []
    if isinstance(data, dict):
        return data.get("tasks") or []
    if isinstance(data, list):
        return data
    return []


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _norm_difficulty(value):
    return value if value in ("simple", "medium", "hard") else "medium"


class PlanTaskViewSet(viewsets.ModelViewSet):
    queryset = PlanTask.objects.select_related("project", "plan", "assignee").all()
    serializer_class = PlanTaskSerializer
    http_method_names = ["get", "post", "patch", "delete"]

    def get_queryset(self):
        qs = self.queryset
        project_id = self.request.query_params.get("project_id")
        plan_id = self.request.query_params.get("plan_id")
        assignee = self.request.query_params.get("assignee")
        status = self.request.query_params.get("status")
        if project_id:
            qs = qs.filter(project_id=project_id)
        if plan_id:
            qs = qs.filter(plan_id=plan_id)
        if assignee:
            qs = qs.filter(assignee_id=assignee)
        if status:
            qs = qs.filter(status=status)
        return qs

    def destroy(self, request, *args, **kwargs):
        task = self.get_object()
        user = request.user
        if not (user.is_superuser or user.role in ("admin", "manager") or task.assignee_id == user.id):
            return Response({"detail": "无权删除该任务"}, status=status.HTTP_403_FORBIDDEN)
        self.perform_destroy(task)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request):
        """导出任务 Excel（按项目）。"""
        project_id = request.query_params.get("project_id")
        if not project_id:
            return Response({"detail": "缺少 project_id"}, status=status.HTTP_400_BAD_REQUEST)
        qs = self.get_queryset().filter(project_id=project_id).order_by("sort_order")

        from io import BytesIO

        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.title = "任务清单"
        ws.append(["任务名称", "业务模块", "所属计划", "难度", "工期(人日)", "负责人", "计划开始", "计划完成", "状态", "描述"])
        for t in qs:
            ws.append(
                [
                    t.title,
                    t.module,
                    t.plan.name if t.plan else "",
                    t.get_difficulty_display(),
                    float(t.estimated_days),
                    t.assignee.username if t.assignee else "",
                    str(t.start_date or ""),
                    str(t.end_date or ""),
                    t.get_status_display(),
                    t.description or "",
                ]
            )
        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)
        response = HttpResponse(
            buf.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="tasks_{project_id}.xlsx"'
        return response
