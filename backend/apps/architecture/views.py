import json

from django.http import StreamingHttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.projects.models import Project
from apps.requirements.models import Requirement
from .arch_gen import base_capability_text, generate_arch_doc, generate_db_sql, generate_doc_stream, generate_sql_stream
from .models import ArchitectureChat, ArchitectureDesign
from .serializers import ArchitectureDesignSerializer, ArchitectureGenerateSerializer

ROLE_PROMPTS = {
    "architect": "你是资深系统架构师，擅长架构设计、技术选型与系统分层设计。",
    "fullstack": "你是资深全栈开发工程师，熟悉前端、后端与数据库，擅长把设计落地为可实施的技术方案。",
}


def _sse(data):
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


class ArchitectureViewSet(viewsets.ModelViewSet):
    queryset = ArchitectureDesign.objects.select_related("project", "created_by").all()
    serializer_class = ArchitectureDesignSerializer
    http_method_names = ["get", "post", "patch", "delete"]

    def get_queryset(self):
        qs = self.queryset
        project_id = self.request.query_params.get("project_id")
        if project_id:
            qs = qs.filter(project_id=project_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user if self.request.user.is_authenticated else None)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        # 架构设计确认保存后，项目自动进入「项目实施」阶段
        design = serializer.instance
        if design.project.status == "architecture":
            design.project.status = "developing"
            design.project.save(update_fields=["status"])
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def destroy(self, request, *args, **kwargs):
        design = self.get_object()
        user = request.user
        if not (user.is_superuser or user.role in ("admin", "manager") or design.created_by_id == user.id):
            return Response({"detail": "无权删除该架构设计"}, status=status.HTTP_403_FORBIDDEN)
        self.perform_destroy(design)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _load_context(self, project_id):
        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            return None, None, Response({"detail": "项目不存在"}, status=status.HTTP_404_NOT_FOUND)
        if project.status == "requirement":
            return project, None, Response(
                {"detail": "请先完成需求分析与项目计划，项目进入「架构设计」状态后再生成架构设计。"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        requirement = Requirement.objects.filter(project=project).order_by("-id").first()
        if not requirement or not requirement.parsed_text:
            return project, None, Response({"detail": "该项目没有可用的需求文档内容，请先完成需求分析。"}, status=status.HTTP_400_BAD_REQUEST)
        return project, requirement, None

    @action(detail=False, methods=["post"], url_path="generate-stream")
    def generate_stream(self, request):
        """流式生成：第一步架构概设文档，第二步数据库 SQL。target: design_doc | sql"""
        serializer = ArchitectureGenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        target = request.data.get("target", "design_doc")
        if target not in ("design_doc", "sql"):
            return Response({"detail": "target 只能是 design_doc 或 sql"}, status=status.HTTP_400_BAD_REQUEST)

        project, requirement, err = self._load_context(data["project_id"])
        if err:
            return err

        def gen():
            try:
                yield _sse({"type": "start"})
                if target == "sql":
                    it = generate_sql_stream(requirement, data["db_type"], data["base_framework"], data.get("constraints", ""), data.get("extra", ""))
                else:
                    it = generate_doc_stream(requirement, data["frontend_stack"], data["backend_stack"], data["base_framework"], data["db_type"], data.get("constraints", ""), data.get("extra", ""))
                for piece in it:
                    yield _sse({"type": "chunk", "content": piece})
                yield _sse({"type": "done"})
            except Exception as e:
                yield _sse({"type": "error", "message": str(e)})

        response = StreamingHttpResponse(gen(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response

    @action(detail=False, methods=["post"], url_path="generate")
    def generate(self, request):
        """（兼容）一次性生成架构设计（非流式）。"""
        serializer = ArchitectureGenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        project, requirement, err = self._load_context(data["project_id"])
        if err:
            return err
        try:
            design_doc = generate_arch_doc(requirement, data["frontend_stack"], data["backend_stack"], data["base_framework"], data["db_type"], data.get("constraints", ""), data.get("extra", ""))
            db_sql = generate_db_sql(requirement, data["db_type"], data["base_framework"], data.get("constraints", ""), data.get("extra", ""))
        except Exception as e:
            return Response({"detail": f"AI 架构设计生成失败：{e}"}, status=status.HTTP_502_BAD_GATEWAY)
        design = ArchitectureDesign.objects.create(
            project=project, frontend_stack=data["frontend_stack"], backend_stack=data["backend_stack"],
            base_framework=data["base_framework"], db_type=data["db_type"], design_doc=design_doc, db_sql=db_sql,
            created_by=request.user if request.user.is_authenticated else None,
        )
        return Response(ArchitectureDesignSerializer(design).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="chat-history")
    def chat_history(self, request, pk=None):
        design = self.get_object()
        thread, _ = ArchitectureChat.objects.get_or_create(design=design)
        return Response({"messages": thread.messages})

    @action(detail=True, methods=["post"], url_path="chat")
    def chat(self, request, pk=None):
        """多轮 AI 对话：可选择角色，支持专家评审。对话历史持久化。"""
        design = self.get_object()
        prompt = (request.data.get("prompt") or "").strip()
        target = request.data.get("target", "design_doc")
        role = request.data.get("role", "architect")
        expert = bool(request.data.get("expert", False))
        if target not in ("design_doc", "sql"):
            return Response({"detail": "target 只能是 design_doc 或 sql"}, status=status.HTTP_400_BAD_REQUEST)
        if role not in ROLE_PROMPTS:
            return Response({"detail": "role 只能是 architect 或 fullstack"}, status=status.HTTP_400_BAD_REQUEST)
        if not prompt:
            return Response({"detail": "请输入内容"}, status=status.HTTP_400_BAD_REQUEST)

        requirement = None
        req_id = request.data.get("requirement_id")
        if req_id:
            requirement = Requirement.objects.filter(id=req_id, project=design.project).first()
        if not requirement:
            requirement = Requirement.objects.filter(project=design.project).order_by("-id").first()
        requirement_text = requirement.parsed_text if requirement else ""

        # 系统提示词：角色 + 是否专家评审
        base = ROLE_PROMPTS[role]
        if expert:
            if target == "sql":
                system = base + " 请作为评审专家，对用户的数据库设计 SQL 进行专业评审，明确指出优点、存在的问题并给出具体修改意见。"
            else:
                system = base + " 请作为评审专家，对用户的架构概设文档进行专业评审，明确指出优点、存在的问题并给出具体修改意见。"
        else:
            system = base + " 请结合用户提供的需求与当前设计/SQL，认真回答用户的修改要求。"

        # 线程历史
        thread, _ = ArchitectureChat.objects.get_or_create(design=design)
        history = list(thread.messages)
        thread.messages = history + [{"role": "user", "content": prompt}]
        thread.save()

        from services import llm

        messages = [{"role": "system", "content": system}]
        # 上下文：需求 + 当前架构概设 + 当前 SQL（保持架构与 SQL 设计一致）+ 选中底座能力介绍
        context = (
            f"需求文档：\n{requirement_text[:500000]}\n\n"
            f"当前架构概设文档：\n{design.design_doc[:500000]}\n\n"
            f"当前数据库 SQL：\n{design.db_sql[:500000]}"
        )
        capability = base_capability_text(design.base_framework)
        if capability:
            context += f"\n\n{capability}"
        messages.append({"role": "user", "content": f"【背景上下文】\n{context}"})
        messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        try:
            reply = llm.chat(messages, temperature=0.4, max_tokens=64000)
        except Exception as e:
            return Response({"detail": f"AI 对话失败：{e}"}, status=status.HTTP_502_BAD_GATEWAY)

        thread.messages = thread.messages + [{"role": "assistant", "content": reply}]
        thread.save()
        return Response({"reply": reply, "messages": thread.messages})

    @action(detail=True, methods=["post"], url_path="chat-stream")
    def chat_stream(self, request, pk=None):
        """流式多轮对话：边生成边返回，中断时已输出内容也保存到历史。"""
        design = self.get_object()
        prompt = (request.data.get("prompt") or "").strip()
        target = request.data.get("target", "design_doc")
        role = request.data.get("role", "architect")
        expert = bool(request.data.get("expert", False))
        if target not in ("design_doc", "sql"):
            return Response({"detail": "target 只能是 design_doc 或 sql"}, status=status.HTTP_400_BAD_REQUEST)
        if role not in ROLE_PROMPTS:
            return Response({"detail": "role 只能是 architect 或 fullstack"}, status=status.HTTP_400_BAD_REQUEST)
        if not prompt:
            return Response({"detail": "请输入内容"}, status=status.HTTP_400_BAD_REQUEST)

        requirement = None
        req_id = request.data.get("requirement_id")
        if req_id:
            requirement = Requirement.objects.filter(id=req_id, project=design.project).first()
        if not requirement:
            requirement = Requirement.objects.filter(project=design.project).order_by("-id").first()
        requirement_text = requirement.parsed_text if requirement else ""

        base = ROLE_PROMPTS[role]
        if expert:
            system = base + (" 请作为评审专家，对用户的数据库设计 SQL 进行专业评审，明确指出优点、存在的问题并给出具体修改意见。"
                             if target == "sql" else
                             " 请作为评审专家，对用户的架构概设文档进行专业评审，明确指出优点、存在的问题并给出具体修改意见。")
        else:
            system = base + " 请结合用户提供的需求与当前设计/SQL，认真回答用户的修改要求。"

        thread, _ = ArchitectureChat.objects.get_or_create(design=design)
        old_history = list(thread.messages)
        # 追加用户消息 + 一个 assistant 占位，边生成边回填
        thread.messages = old_history + [{"role": "user", "content": prompt}, {"role": "assistant", "content": ""}]
        thread.save()

        from services import llm

        # 上下文：需求 + 当前架构概设 + 当前 SQL（保持架构与 SQL 设计一致）+ 选中底座能力介绍
        context = (
            f"需求文档：\n{requirement_text[:500000]}\n\n"
            f"当前架构概设文档：\n{design.design_doc[:500000]}\n\n"
            f"当前数据库 SQL：\n{design.db_sql[:500000]}"
        )
        capability = base_capability_text(design.base_framework)
        if capability:
            context += f"\n\n{capability}"
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": f"【背景上下文】\n{context}"},
        ]
        messages.extend(old_history)
        messages.append({"role": "user", "content": prompt})

        def gen():
            acc = ""

            def persist():
                msgs = list(thread.messages)
                msgs[-1]["content"] = acc
                thread.messages = msgs
                thread.save(update_fields=["messages"])

            try:
                yield _sse({"type": "start"})
                for piece in llm.chat_stream(messages, temperature=0.4, max_tokens=64000):
                    acc += piece
                    yield _sse({"type": "chunk", "content": piece})
                    persist()  # 每块即保存，中断也不丢已输出内容
                yield _sse({"type": "done"})
            except Exception as e:
                yield _sse({"type": "error", "message": str(e)})
            finally:
                persist()  # 客户端中断时也把已输出内容落库

        response = StreamingHttpResponse(gen(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response
