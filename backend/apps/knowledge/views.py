import json

from django.db import transaction
from django.http import StreamingHttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.architecture.models import ArchitectureDesign
from apps.operation.models import OperationItem, OperationMetric
from apps.project_planning.models import PlanTask, ProjectPlan
from apps.projects.models import Project
from services import document_parser, vector_store
from .knowledge_gen import organize_knowledge
from .models import KnowledgeItem
from .serializers import KnowledgeAddSerializer, KnowledgeItemSerializer, KnowledgeSearchSerializer


def _sse(data):
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


class KnowledgeViewSet(viewsets.ModelViewSet):
    queryset = KnowledgeItem.objects.select_related("created_by").all()
    serializer_class = KnowledgeItemSerializer

    def get_queryset(self):
        qs = self.queryset
        project_id = self.request.query_params.get("project_id")
        if project_id:
            qs = qs.filter(project_id=project_id)
        return qs

    def destroy(self, request, *args, **kwargs):
        """删除知识条目并同步清理其向量（避免脏数据/重复影响检索）。"""
        item = self.get_object()
        vector_store.delete_knowledge_by_metadata(item.project_id, {"item_id": item.id})
        self.perform_destroy(item)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _add_knowledge(self, project, text, user, source="manual", vec_type="knowledge"):
        """写入知识条目并向量化。source 标记来源（如 ingest:plan），vec_type 对应向量元数据 type。"""
        with transaction.atomic():
            item = KnowledgeItem.objects.create(
                project=project, content=text, source=source, created_by=user if user.is_authenticated else None
            )
            chunks = document_parser.chunk_text(text)
            metadatas = [{"source": text[:30], "type": vec_type, "item_id": item.id} for _ in chunks]
            ids = [f"item{item.id}_c{i}" for i in range(len(chunks))]
            vector_store.add_knowledge(project.id, chunks, metadatas, ids)

    def _build_context(self, kind, project):
        """按环节聚合原始文档内容，供 AI 整理。"""
        if kind == "plan":
            parts = []
            for p in ProjectPlan.objects.filter(project=project):
                members = "、".join(f"{m.user.username}(权重{m.weight})" for m in p.members.select_related("user"))
                parts.append(
                    f"【计划】{p.name}\n周期：{p.start_date} ~ {p.launch_date}\n成员：{members}\n内容：\n{p.plan_content}"
                )
            return "\n\n".join(parts)
        if kind == "task":
            parts = []
            for t in PlanTask.objects.filter(project=project).order_by("sort_order"):
                parts.append(
                    f"【任务】{t.title}（模块：{t.module or '-'}，负责人：{t.assignee.username if t.assignee else '未指派'}，"
                    f"状态：{t.get_status_display()}，工期：{t.estimated_days}人日，{t.start_date}~{t.end_date}）\n{t.description}"
                )
            return "\n\n".join(parts)
        if kind == "architecture":
            parts = []
            for d in ArchitectureDesign.objects.filter(project=project):
                parts.append(
                    f"【架构设计】前端：{d.frontend_stack}；后端：{d.backend_stack}；底座：{d.get_base_framework_display()}；"
                    f"数据库：{d.get_db_type_display()}\n【架构概设】\n{d.design_doc}\n【数据库SQL】\n{d.db_sql}"
                )
            return "\n\n".join(parts)
        if kind == "operation":
            parts = []
            for it in OperationItem.objects.filter(project=project):
                parts.append(
                    f"【{it.get_category_display()}】{it.title}（优先级：{it.get_priority_display()}，状态：{it.get_status_display()}，提出人：{it.requestor or '-'}）\n{it.content}"
                )
            metrics = OperationMetric.objects.filter(project=project)
            if metrics:
                parts.append("【运营指标】")
                for m in metrics:
                    parts.append(f"- {m.month} {m.get_indicator_display()}：{m.value}（{m.note or ''}）")
            return "\n\n".join(parts)
        return ""

    @action(detail=False, methods=["post"], url_path="add")
    def add(self, request):
        """开发过程中向项目知识库新增知识。"""
        serializer = KnowledgeAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        project_id = serializer.validated_data["project_id"]
        text = serializer.validated_data["text"]
        if not text.strip():
            return Response({"detail": "text 不能为空"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            return Response({"detail": "项目不存在"}, status=status.HTTP_404_NOT_FOUND)

        self._add_knowledge(project, text, request.user)
        item = KnowledgeItem.objects.filter(project=project).order_by("-id").first()
        return Response(KnowledgeItemSerializer(item).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="search")
    def search(self, request):
        """语义检索项目知识库。"""
        serializer = KnowledgeSearchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        project_id = serializer.validated_data["project_id"]
        query = serializer.validated_data["query"]
        top_k = serializer.validated_data["top_k"]
        results = vector_store.search_knowledge(project_id, query, top_k=top_k)
        return Response({"results": results})

    @action(detail=False, methods=["get"], url_path="all")
    def all(self, request):
        """列出项目知识库全部内容（需求初始知识 + 开发新增知识）。"""
        project_id = request.query_params.get("project_id")
        if not project_id:
            return Response({"detail": "缺少 project_id"}, status=status.HTTP_400_BAD_REQUEST)
        items = vector_store.list_knowledge(int(project_id))
        return Response({"items": items, "count": len(items)})

    @action(detail=False, methods=["post"], url_path="ingest")
    def ingest(self, request):
        """知识入库：AI 整理某环节（计划/任务/架构）的相关文档并写入知识库。"""
        kind = request.data.get("kind")
        project_id = request.data.get("project_id")
        if kind not in ("plan", "task", "architecture", "operation"):
            return Response({"detail": "kind 只能是 plan/task/architecture/operation"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            project = Project.objects.get(id=project_id)
        except (Project.DoesNotExist, TypeError):
            return Response({"detail": "项目不存在"}, status=status.HTTP_404_NOT_FOUND)

        context = self._build_context(kind, project)
        if not context.strip():
            return Response({"detail": "该环节暂无内容可入库"}, status=status.HTTP_400_BAD_REQUEST)

        # 覆盖式入库：先删除该环节此前的入库知识（记录 + 向量），避免重复/过期信息
        source_key = f"ingest:{kind}"
        old_ids = list(KnowledgeItem.objects.filter(project=project, source=source_key).values_list("id", flat=True))
        if old_ids:
            KnowledgeItem.objects.filter(project=project, source=source_key).delete()
        vector_store.delete_knowledge_by_metadata(project.id, {"type": source_key})

        try:
            items = organize_knowledge(kind, project.name, context)
        except Exception as e:
            return Response({"detail": f"AI 整理失败：{e}"}, status=status.HTTP_502_BAD_GATEWAY)

        created = []
        for it in items:
            text = str(it.get("content") or "").strip()
            if not text:
                continue
            title = str(it.get("title") or "")[:30]
            self._add_knowledge(project, f"{title}：{text}", request.user, source=source_key, vec_type=source_key)
            created.append(title)
        return Response({"created": len(created), "overwritten": len(old_ids), "titles": created})

    @action(detail=False, methods=["post"], url_path="clear")
    def clear(self, request):
        """清空指定项目的知识库：删除向量 collection 与该项目的知识条目记录。

        仅管理员/项目负责人/项目经理可操作。用于切换 embedding 模型后重建向量库。
        """
        project_id = request.data.get("project_id")
        try:
            project = Project.objects.get(id=project_id)
        except (Project.DoesNotExist, TypeError, ValueError):
            return Response({"detail": "项目不存在"}, status=status.HTTP_404_NOT_FOUND)
        user = request.user
        can_clear = (
            user.is_superuser
            or getattr(user, "role", None) == "admin"
            or project.owner_id == user.id
            or project.member_links.filter(user=user, role="manager").exists()
        )
        if not can_clear:
            return Response(
                {"detail": "仅管理员、项目负责人或项目经理可清空知识库"},
                status=status.HTTP_403_FORBIDDEN,
            )
        deleted_items, _ = KnowledgeItem.objects.filter(project=project).delete()
        vector_store.delete_project_knowledge(project.id)
        return Response({"cleared_items": deleted_items})

    @action(detail=False, methods=["post"], url_path="qa")
    def qa(self, request):
        """知识问答：检索知识库 → AI 基于知识库回答（支持会话记忆）。"""
        from services import llm

        project_id = request.data.get("project_id")
        question = (request.data.get("question") or "").strip()
        history = request.data.get("history") or []
        if not project_id or not question:
            return Response({"detail": "缺少 project_id 或 question"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            return Response({"detail": "项目不存在"}, status=status.HTTP_404_NOT_FOUND)

        results = vector_store.search_knowledge(int(project_id), question, top_k=5)
        if results:
            context = "\n\n".join(f"[{i+1}] {r['text']}" for i, r in enumerate(results))
        else:
            context = "（知识库中暂无相关内容）"

        system = (
            "你是企业知识库问答助手。请严格基于下面提供的【知识库内容】回答用户问题，"
            "答案要准确、条理清晰。如果知识库中没有相关信息，请明确说明“知识库中未找到相关内容”，不要编造。\n\n"
            f"【知识库内容】\n{context}"
        )
        messages = [{"role": "system", "content": system}]
        for h in history[-6:]:
            if h.get("role") in ("user", "assistant"):
                messages.append({"role": h["role"], "content": str(h.get("content", ""))})
        messages.append({"role": "user", "content": question})

        try:
            answer = llm.chat(messages, temperature=0.3)
        except Exception as e:
            return Response({"detail": f"AI 回答失败：{e}"}, status=status.HTTP_502_BAD_GATEWAY)

        refs = [
            {"text": r["text"], "distance": r.get("distance"), "type": r.get("metadata", {}).get("type", "")}
            for r in results
        ]
        return Response({"answer": answer, "refs": refs})

    @action(detail=False, methods=["post"], url_path="qa-stream")
    def qa_stream(self, request):
        """知识问答（流式）：检索知识库 → AI 流式回答。"""
        from services import llm

        project_id = request.data.get("project_id")
        question = (request.data.get("question") or "").strip()
        history = request.data.get("history") or []
        if not project_id or not question:
            return Response({"detail": "缺少 project_id 或 question"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            return Response({"detail": "项目不存在"}, status=status.HTTP_404_NOT_FOUND)

        results = vector_store.search_knowledge(int(project_id), question, top_k=5)
        context = "\n\n".join(f"[{i+1}] {r['text']}" for i, r in enumerate(results)) if results else "（知识库中暂无相关内容）"
        system = (
            "你是企业知识库问答助手。请严格基于下面提供的【知识库内容】回答用户问题，"
            "答案要准确、条理清晰。如果知识库中没有相关信息，请明确说明“知识库中未找到相关内容”，不要编造。\n\n"
            f"【知识库内容】\n{context}"
        )
        messages = [{"role": "system", "content": system}]
        for h in history[-6:]:
            if h.get("role") in ("user", "assistant"):
                messages.append({"role": h["role"], "content": str(h.get("content", ""))})
        messages.append({"role": "user", "content": question})

        def gen():
            try:
                yield _sse({"type": "start"})
                for piece in llm.chat_stream(messages, temperature=0.3, max_tokens=4096):
                    yield _sse({"type": "chunk", "content": piece})
                yield _sse({"type": "done"})
            except Exception as e:
                yield _sse({"type": "error", "message": str(e)})

        response = StreamingHttpResponse(gen(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response
