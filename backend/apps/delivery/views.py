from django.db import models
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.projects.models import Project
from .models import DeliveryDoc, normalize_doc_type
from .serializers import DeliveryDocContentUploadSerializer, DeliveryDocSerializer


class DeliveryDocViewSet(viewsets.ModelViewSet):
    queryset = DeliveryDoc.objects.select_related("project", "created_by").all()
    serializer_class = DeliveryDocSerializer

    def get_queryset(self):
        qs = self.queryset
        project_id = self.request.query_params.get("project_id")
        if project_id:
            qs = qs.filter(project_id=project_id)
        keyword = (self.request.query_params.get("keyword") or "").strip()
        if keyword:
            qs = qs.filter(
                models.Q(title__icontains=keyword)
                | models.Q(doc_type__icontains=keyword)
                | models.Q(content__icontains=keyword)
            )
        return qs

    def destroy(self, request, *args, **kwargs):
        """删除交付文档：仅管理员/项目经理或文档创建者本人。"""
        doc = self.get_object()
        user = request.user
        if not (user.is_superuser or user.role in ("admin", "manager") or doc.created_by_id == user.id):
            return Response({"detail": "无权删除该文档"}, status=status.HTTP_403_FORBIDDEN)
        # 删除附件文件，避免残留
        if doc.file:
            doc.file.delete(save=False)
        self.perform_destroy(doc)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _save(self, project, title, doc_type, content, source, file=None):
        return DeliveryDoc.objects.create(
            project=project,
            title=title,
            doc_type=normalize_doc_type(doc_type),
            content=content or "",
            file=file,
            source=source,
            created_by=self.request.user if self.request.user.is_authenticated else None,
        )

    @action(detail=False, methods=["post"], url_path="upload")
    def upload(self, request):
        """上传交付文档：支持 Agent 内容回传 或 手动文件上传。"""
        # 方式1：内容回传（Agent 插件调用）
        if request.data.get("project_id") and request.data.get("content") is not None:
            serializer = DeliveryDocContentUploadSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            try:
                project = Project.objects.get(id=serializer.validated_data["project_id"])
            except Project.DoesNotExist:
                return Response({"detail": "项目不存在"}, status=status.HTTP_404_NOT_FOUND)
            doc = self._save(
                project,
                serializer.validated_data["title"],
                serializer.validated_data.get("type", ""),
                serializer.validated_data["content"],
                source="agent",
            )
            return Response(DeliveryDocSerializer(doc).data, status=status.HTTP_201_CREATED)

        # 方式2：手动文件上传
        project_id = request.data.get("project_id")
        file = request.FILES.get("file")
        if not project_id or not file:
            return Response({"detail": "缺少 project_id 或 file"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            return Response({"detail": "项目不存在"}, status=status.HTTP_404_NOT_FOUND)
        title = request.data.get("title") or file.name
        doc = self._save(
            project,
            title,
            request.data.get("type", ""),
            "",
            source="manual",
            file=file,
        )
        return Response(DeliveryDocSerializer(doc).data, status=status.HTTP_201_CREATED)
