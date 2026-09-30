from django.contrib.auth import get_user_model
from django.db.models import Count
from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import user_can_access_project
from apps.architecture.models import ArchitectureDesign
from apps.delivery.models import DeliveryDoc
from apps.project_planning.models import PlanTask
from apps.projects.models import Project
from apps.requirements.models import Requirement
from .models import Bug, BugImage, TestCase, TestTask
from .serializers import (
    BugFromTestSerializer,
    BugSerializer,
    TestCaseSerializer,
    TestTaskBatchDispatchSerializer,
    TestTaskCreateSerializer,
    TestTaskSerializer,
)
from .test_gen import generate_report, generate_test_cases

User = get_user_model()


class TestCaseViewSet(viewsets.ModelViewSet):
    queryset = TestCase.objects.select_related("project").all()
    serializer_class = TestCaseSerializer

    def get_queryset(self):
        qs = self.queryset
        project_id = self.request.query_params.get("project_id")
        module = self.request.query_params.get("module")
        priority = self.request.query_params.get("priority")
        if project_id:
            qs = qs.filter(project_id=project_id)
        if module:
            qs = qs.filter(module__icontains=module)
        if priority:
            qs = qs.filter(priority=priority)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=["post"], url_path="generate")
    def generate(self, request):
        """AI 生成测试用例：参考【需求文档 + 架构设计 + 计划任务拆分】多来源，贴合实现。"""
        project_id = request.data.get("project_id")
        module = (request.data.get("module") or "").strip()
        source = request.data.get("source", "requirement")
        task_id = request.data.get("task_id")
        task_ids = request.data.get("task_ids") or []
        if task_id:
            task_ids = list(task_ids) + [task_id]
        task_ids = [int(t) for t in task_ids if str(t).isdigit()]

        try:
            project = Project.objects.get(id=project_id)
        except (Project.DoesNotExist, TypeError):
            return Response({"detail": "项目不存在"}, status=status.HTTP_404_NOT_FOUND)

        # 选中任务（支持多选）
        selected_tasks = []
        if source == "task" and task_ids:
            selected_tasks = list(
                PlanTask.objects.select_related("plan__requirement").filter(id__in=task_ids, project=project)
            )
            if not selected_tasks:
                return Response({"detail": "所选开发任务不存在"}, status=status.HTTP_400_BAD_REQUEST)

        # 1) 对应需求文档（优先手动指定的 requirement_id，其次选中任务所属计划需求，最后取最新）
        requirement = None
        req_id = request.data.get("requirement_id")
        if req_id:
            requirement = Requirement.objects.filter(id=req_id, project=project).first()
        if not requirement and selected_tasks:
            for t in selected_tasks:
                if t.plan and t.plan.requirement_id:
                    requirement = t.plan.requirement
                    break
        if not requirement:
            requirement = Requirement.objects.filter(project=project).order_by("-id").first()
        if not requirement or not requirement.parsed_text:
            return Response({"detail": "该项目没有可用的需求文档内容，请先完成需求分析。"}, status=status.HTTP_400_BAD_REQUEST)

        parts = [f"【需求文档】{requirement.title}\n{requirement.parsed_text}"]

        # 2) 架构设计（最新一份：技术栈 + 概设 + SQL）
        arch = ArchitectureDesign.objects.filter(project=project).order_by("-id").first()
        if arch:
            arch_parts = [
                f"【架构设计】前端:{arch.frontend_stack} 后端:{arch.backend_stack} "
                f"框架底座:{arch.get_base_framework_display()} 数据库:{arch.get_db_type_display()}",
            ]
            if arch.design_doc:
                arch_parts.append(f"架构概设文档：\n{arch.design_doc}")
            if arch.db_sql:
                arch_parts.append(f"数据库SQL：\n{arch.db_sql}")
            parts.append("\n\n".join(arch_parts))

        # 3) 计划任务拆分（任务来源：所选任务所属计划的任务；需求来源：项目全部任务）
        if selected_tasks:
            plan_ids = {t.plan_id for t in selected_tasks if t.plan_id}
            tasks = PlanTask.objects.filter(plan_id__in=plan_ids) if plan_ids else PlanTask.objects.none()
        else:
            tasks = PlanTask.objects.filter(project=project)
        tasks = tasks.select_related("assignee").order_by("sort_order")
        if tasks.exists():
            lines = ["【计划任务拆分】"]
            for t in tasks:
                lines.append(
                    f"- [{t.module or '未分组'}] {t.title}（负责人：{t.assignee.username if t.assignee else '-'}，"
                    f"难度：{t.get_difficulty_display()}）：{t.description or ''}"
                )
            parts.append("\n".join(lines))

        # 4) 目标任务重点（任务来源时，列出所有选中任务）
        if selected_tasks:
            lines = ["【本次重点生成用例的目标任务】"]
            for t in selected_tasks:
                lines.append(f"- {t.title}：{t.description or ''}")
            parts.append("\n".join(lines))

        context = "\n\n".join(parts)
        try:
            cases = generate_test_cases(context, module)
        except Exception as e:
            return Response({"detail": f"AI 生成失败：{e}"}, status=status.HTTP_502_BAD_GATEWAY)
        return Response({"cases": cases})

    def destroy(self, request, *args, **kwargs):
        case = self.get_object()
        user = request.user
        if not (user.is_superuser or user.role in ("admin", "manager") or case.created_by_id == user.id):
            return Response({"detail": "无权删除该用例"}, status=status.HTTP_403_FORBIDDEN)
        self.perform_destroy(case)
        return Response(status=status.HTTP_204_NO_CONTENT)


class TestTaskViewSet(viewsets.ModelViewSet):
    queryset = TestTask.objects.select_related("test_case", "assignee").all()
    serializer_class = TestTaskSerializer

    def get_queryset(self):
        qs = self.queryset
        project_id = self.request.query_params.get("project_id")
        assignee = self.request.query_params.get("assignee")
        status = self.request.query_params.get("status")
        module = self.request.query_params.get("module")
        if project_id:
            qs = qs.filter(test_case__project_id=project_id)
        if assignee:
            qs = qs.filter(assignee_id=assignee)
        if status:
            qs = qs.filter(status=status)
        if module:
            qs = qs.filter(test_case__module__icontains=module)
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
        """导出测试任务 Excel（按项目）。"""
        project_id = request.query_params.get("project_id")
        if not project_id:
            return Response({"detail": "缺少 project_id"}, status=status.HTTP_400_BAD_REQUEST)
        qs = self.get_queryset().filter(test_case__project_id=project_id).order_by("created_at")

        from io import BytesIO

        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.title = "测试任务"
        ws.append(["用例名称", "所属模块", "执行人", "状态", "结果/说明", "创建时间", "更新时间"])
        for t in qs:
            ws.append(
                [
                    t.test_case.name,
                    t.test_case.module or "",
                    t.assignee.username,
                    t.get_status_display(),
                    t.result or "",
                    str(t.created_at),
                    str(t.updated_at),
                ]
            )
        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)
        response = HttpResponse(
            buf.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="test_tasks_{project_id}.xlsx"'
        return response

    @action(detail=False, methods=["post"], url_path="dispatch")
    def assign(self, request):
        """派单：为用例创建测试任务并指派。"""
        serializer = TestTaskCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            test_case = TestCase.objects.get(id=serializer.validated_data["test_case_id"])
        except TestCase.DoesNotExist:
            return Response({"detail": "测试用例不存在"}, status=status.HTTP_404_NOT_FOUND)
        if not user_can_access_project(request.user, test_case.project):
            return Response({"detail": "无权访问该项目"}, status=status.HTTP_403_FORBIDDEN)
        try:
            assignee = User.objects.get(id=serializer.validated_data["assignee_id"])
        except User.DoesNotExist:
            return Response({"detail": "指派用户不存在"}, status=status.HTTP_404_NOT_FOUND)

        # 同一用例已派给同一人则复用，避免重复创建任务
        existing = TestTask.objects.filter(test_case=test_case, assignee=assignee).first()
        if existing:
            return Response(TestTaskSerializer(existing).data, status=status.HTTP_200_OK)
        task = TestTask.objects.create(test_case=test_case, assignee=assignee, status="pending")
        return Response(TestTaskSerializer(task).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="batch-dispatch")
    def batch_dispatch(self, request):
        """批量派单：多个用例一次性指派给同一执行人（已存在则复用，容忍历史重复数据）。"""
        serializer = TestTaskBatchDispatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            assignee = User.objects.get(id=serializer.validated_data["assignee_id"])
        except User.DoesNotExist:
            return Response({"detail": "指派用户不存在"}, status=status.HTTP_404_NOT_FOUND)

        cases = TestCase.objects.filter(id__in=serializer.validated_data["test_case_ids"])
        # 校验：所选用例须属于当前用户可访问的项目（成员/负责人/管理员）
        for tc in cases:
            if not user_can_access_project(request.user, tc.project):
                return Response({"detail": f"无权访问用例「{tc.name}」所属项目"}, status=status.HTTP_403_FORBIDDEN)
        created = []
        for tc in cases:
            task = TestTask.objects.filter(test_case=tc, assignee=assignee).first()
            if task is None:
                task = TestTask.objects.create(test_case=tc, assignee=assignee, status="pending")
            created.append(task)
        return Response(TestTaskSerializer(created, many=True).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], url_path="statistics")
    def statistics(self, request):
        """测试统计：用例/任务规模、通过率、优先级与模块分布。"""
        project_id = request.query_params.get("project_id")
        cases = TestCase.objects.all()
        tasks = TestTask.objects.all()
        if project_id:
            cases = cases.filter(project_id=project_id)
            tasks = tasks.filter(test_case__project_id=project_id)

        by_status = {k: tasks.filter(status=k).count() for k, _ in TestTask.STATUS_CHOICES}
        total_tasks = sum(by_status.values())
        passed = by_status.get("passed", 0)
        pass_rate = round(passed / total_tasks * 100, 1) if total_tasks else 0.0
        by_priority = {k: cases.filter(priority=k).count() for k, _ in TestCase.PRIORITY_CHOICES}
        by_module = [
            {"module": r["module"] or "未分组", "count": r["c"]}
            for r in cases.values("module").annotate(c=Count("id")).order_by("-c")[:10]
        ]
        return Response(
            {
                "total_cases": cases.count(),
                "total_tasks": total_tasks,
                "pass_rate": pass_rate,
                "by_status": by_status,
                "by_priority": by_priority,
                "by_module": by_module,
            }
        )

    @action(detail=False, methods=["post"], url_path="report")
    def report(self, request):
        """生成测试报告并写入交付文档；通过率达标且处于开发中则推进项目到「项目交付」。"""
        project_id = request.data.get("project_id")
        try:
            project = Project.objects.get(id=project_id)
        except (Project.DoesNotExist, TypeError):
            return Response({"detail": "项目不存在"}, status=status.HTTP_404_NOT_FOUND)

        cases = TestCase.objects.filter(project=project)
        tasks = TestTask.objects.filter(test_case__project=project)
        by_status = {k: tasks.filter(status=k).count() for k, _ in TestTask.STATUS_CHOICES}
        total_tasks = sum(by_status.values())
        passed = by_status.get("passed", 0)
        pass_rate = round(passed / total_tasks * 100, 1) if total_tasks else 0.0
        by_priority = {k: cases.filter(priority=k).count() for k, _ in TestCase.PRIORITY_CHOICES}
        failed_items = [
            {"case": t.test_case.name, "status": t.get_status_display(), "result": t.result or ""}
            for t in tasks.filter(status__in=["failed", "blocked"])
        ]

        stats = {
            "total_cases": cases.count(),
            "total_tasks": total_tasks,
            "pass_rate": pass_rate,
            "by_status": by_status,
            "by_priority": by_priority,
        }
        try:
            report_text = generate_report(project.name, stats, failed_items)
        except Exception as e:
            return Response({"detail": f"AI 报告生成失败：{e}"}, status=status.HTTP_502_BAD_GATEWAY)

        doc = DeliveryDoc.objects.create(
            project=project,
            title=f"{project.name} 测试报告",
            doc_type="testing",
            content=report_text,
            source="manual",
            created_by=request.user if request.user.is_authenticated else None,
        )

        advanced = False
        if pass_rate >= 90 and project.status == "developing":
            project.status = "delivery"
            project.save(update_fields=["status"])
            advanced = True

        return Response(
            {
                "delivery_doc_id": doc.id,
                "title": doc.title,
                "pass_rate": pass_rate,
                "total_tasks": total_tasks,
                "advanced": advanced,
                "content": report_text,
            }
        )


class BugViewSet(viewsets.ModelViewSet):
    queryset = Bug.objects.select_related("project", "assignee", "reporter", "related_test_task", "related_task").all()
    serializer_class = BugSerializer

    def get_queryset(self):
        qs = self.queryset
        project_id = self.request.query_params.get("project_id")
        status = self.request.query_params.get("status")
        assignee = self.request.query_params.get("assignee")
        severity = self.request.query_params.get("severity")
        if project_id:
            qs = qs.filter(project_id=project_id)
        if status:
            qs = qs.filter(status=status)
        if assignee:
            qs = qs.filter(assignee_id=assignee)
        if severity:
            qs = qs.filter(severity=severity)
        return qs

    def perform_create(self, serializer):
        serializer.save(reporter=self.request.user if self.request.user.is_authenticated else None)

    def perform_update(self, serializer):
        # 关联了开发任务且未填业务模块时，自动带出任务模块
        data = serializer.validated_data
        if not data.get("module") and data.get("related_task") and data["related_task"].module:
            data["module"] = data["related_task"].module
        serializer.save()

    @action(detail=True, methods=["post"], url_path="upload-image")
    def upload_image(self, request, pk=None):
        """上传缺陷截图（multipart: image 文件）。"""
        bug = self.get_object()
        image = request.FILES.get("image")
        if not image:
            return Response({"detail": "缺少 image 文件"}, status=status.HTTP_400_BAD_REQUEST)
        BugImage.objects.create(bug=bug, image=image)
        return Response(BugSerializer(bug).data)

    @action(detail=True, methods=["post"], url_path="delete-image")
    def delete_image(self, request, pk=None):
        """删除缺陷图片。"""
        bug = self.get_object()
        image_id = request.data.get("image_id")
        BugImage.objects.filter(bug=bug, id=image_id).delete()
        return Response(BugSerializer(bug).data)

    def destroy(self, request, *args, **kwargs):
        bug = self.get_object()
        user = request.user
        if not (user.is_superuser or user.role in ("admin", "manager") or bug.reporter_id == user.id or bug.assignee_id == user.id):
            return Response({"detail": "无权删除该缺陷"}, status=status.HTTP_403_FORBIDDEN)
        self.perform_destroy(bug)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"], url_path="statistics")
    def statistics(self, request):
        """缺陷统计：数量/未关闭/按状态与严重程度分布。"""
        project_id = request.query_params.get("project_id")
        qs = Bug.objects.all()
        if project_id:
            qs = qs.filter(project_id=project_id)
        by_status = {k: qs.filter(status=k).count() for k, _ in Bug.STATUS_CHOICES}
        by_severity = {k: qs.filter(severity=k).count() for k, _ in Bug.SEVERITY_CHOICES}
        total = qs.count()
        open_count = total - by_status.get("closed", 0)
        return Response(
            {
                "total": total,
                "open": open_count,
                "by_status": by_status,
                "by_severity": by_severity,
            }
        )

    @action(detail=False, methods=["post"], url_path="from-test-task")
    def from_test_task(self, request):
        """从失败/阻塞的测试任务一键转缺陷。"""
        serializer = BugFromTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            task = TestTask.objects.select_related("test_case", "assignee").get(id=serializer.validated_data["test_task_id"])
        except TestTask.DoesNotExist:
            return Response({"detail": "测试任务不存在"}, status=status.HTTP_404_NOT_FOUND)
        if not user_can_access_project(request.user, task.test_case.project):
            return Response({"detail": "无权访问该项目"}, status=status.HTTP_403_FORBIDDEN)

        assignee = None
        if serializer.validated_data.get("assignee_id"):
            try:
                assignee = User.objects.get(id=serializer.validated_data["assignee_id"])
            except User.DoesNotExist:
                return Response({"detail": "处理人不存在"}, status=status.HTTP_404_NOT_FOUND)

        title = serializer.validated_data.get("title") or f"{task.test_case.name} 执行失败"
        bug = Bug.objects.create(
            project=task.test_case.project,
            title=title,
            module=serializer.validated_data.get("module") or task.test_case.module or "",
            description=f"来源：测试用例「{task.test_case.name}」\n测试结果：{task.result or ''}",
            severity=serializer.validated_data["severity"],
            assignee=assignee or task.assignee,
            related_test_task=task,
            reporter=request.user if request.user.is_authenticated else None,
        )
        return Response(BugSerializer(bug).data, status=status.HTTP_201_CREATED)
