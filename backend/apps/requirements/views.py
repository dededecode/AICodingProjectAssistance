import logging
import os
import re

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from rest_framework import status, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.projects.models import Project
from services import document_parser, vector_store
from .analysis import analyze_requirement
from .image_naming import name_document_images
from .models import PrototypeImage, Requirement
from .serializers import PrototypeImageSerializer, RequirementSerializer

logger = logging.getLogger(__name__)

_INVALID_NAME_CHARS = re.compile(r'[\\/:*?"<>|\r\n]')


def _map_purpose_to_kind(purpose: str, name: str = "") -> str:
    """把 AI 图片用途映射为类型：UI图->ui、业务流程图->flow、原型图->prototype、无法判断->other。"""
    p = (purpose or "").strip().lower()
    n = (name or "").strip().lower()
    text = f"{p} {n}"
    if p == "ui" or "ui图" in text or n.endswith("ui图"):
        return "ui"
    if any(k in text for k in ("流程图", "时序图", "数据流", "状态图", "活动图", "架构图")):
        return "flow"
    if "原型" in text or "线框" in text:
        return "prototype"
    return "other"


def _save_images_as_prototypes(requirement, doc_text, images, uploader):
    """把图文文档抽取的图片入库为原型图/UI 图（AI 按「端-模块名-功能名-用途」取名）。

    容错：AI 取名失败回退默认名；名称重复自动加 -2/-3 序号。返回创建数量。
    """
    if not images:
        return 0
    # AI 取名（失败则全部回退默认名，不阻塞上传）
    try:
        named = name_document_images(doc_text, images)
        logger.info("[图片入库] AI 取名完成：%s 张 -> %s", len(images), [n["name"] for n in named])
    except Exception as e:
        logger.warning("[图片入库] AI 取名失败，使用默认名称：%s", e)
        named = []

    existing = set(
        PrototypeImage.objects.filter(project=requirement.project).values_list("name", flat=True)
    )
    created = 0
    for i, info in enumerate(images, start=1):
        name = ""
        purpose = ""
        for item in named:
            if item.get("index") == i and item.get("name"):
                name = _INVALID_NAME_CHARS.sub("_", item["name"])[:100].strip("_ ")
                purpose = item.get("purpose", "")
                break
        if not name:
            name = f"{requirement.title}-配图-{i}"[:100]
        # 项目内唯一：重复自动加序号
        base, seq = name, 2
        while name in existing:
            suffix = f"-{seq}"
            name = f"{base[: 100 - len(suffix)]}{suffix}"
            seq += 1
        existing.add(name)

        ext = os.path.splitext(info.get("file", ""))[1] or ".png"
        try:
            with open(info["path"], "rb") as f:
                content = f.read()
        except OSError as e:
            logger.warning("[图片入库] 读取图片文件失败，跳过第 %s 张：%s", i, e)
            continue
        # kind 映射：UI图->ui、业务流程图->flow、原型图->prototype、无法判断->other
        PrototypeImage.objects.create(
            project=requirement.project,
            name=name,
            kind=_map_purpose_to_kind(purpose, name),
            image=ContentFile(content, name=f"{name}{ext}"),
            uploader=uploader,
        )
        created += 1
    logger.info("[图片入库] 已将 %s 张文档图片保存到原型图库（项目 %s）", created, requirement.project_id)
    return created


class RequirementViewSet(viewsets.ModelViewSet):
    queryset = Requirement.objects.select_related("project").all()
    serializer_class = RequirementSerializer

    def get_queryset(self):
        qs = self.queryset
        project_id = self.request.query_params.get("project_id")
        if project_id:
            qs = qs.filter(project_id=project_id)
        return qs

    def destroy(self, request, *args, **kwargs):
        """删除需求文档：同步清理向量、磁盘文件与解析图片。"""
        import shutil

        requirement = self.get_object()
        vector_store.delete_knowledge_by_metadata(requirement.project_id, {"requirement_id": requirement.id})

        for p in [requirement.file_path, requirement.original_file.path if requirement.original_file else None]:
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass
        image_dir = os.path.join(settings.MEDIA_ROOT, "requirements", "images", str(requirement.id))
        if os.path.isdir(image_dir):
            shutil.rmtree(image_dir, ignore_errors=True)

        self.perform_destroy(requirement)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["post"], url_path="upload")
    def upload(self, request):
        """上传需求文档并解析入库（不确认）。"""
        project_id = request.data.get("project_id")
        file = request.FILES.get("file")
        if not project_id or not file:
            return Response({"detail": "缺少 project_id 或 file"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            return Response({"detail": "项目不存在"}, status=status.HTTP_404_NOT_FOUND)

        filename = file.name
        title = request.data.get("title") or os.path.splitext(filename)[0]
        doc_type = request.data.get("doc_type", "text")
        dest_dir = os.path.join(settings.MEDIA_ROOT, "requirements")
        file_path = document_parser.save_upload(file, dest_dir, filename)

        # 先创建记录占位，图文解析需要 requirement.id 作为图片存储目录
        requirement = Requirement.objects.create(
            project=project,
            title=title,
            original_file=file,
            file_path=file_path,
            parsed_text="",
        )

        if doc_type == "rich" and filename.lower().endswith(".docx"):
            # 图文 Word：抽取图片存储，文本中保留图片引用标记（不进行 AI 回写）
            image_dir = os.path.join(settings.MEDIA_ROOT, "requirements", "images", str(requirement.id))
            rel_prefix = f"requirements/images/{requirement.id}"
            try:
                text, images = document_parser.parse_docx_rich(file_path, image_dir, rel_prefix)
            except Exception as e:
                requirement.delete()
                return Response({"detail": f"图文文档解析失败：{e}"}, status=status.HTTP_400_BAD_REQUEST)
            requirement.parsed_text = text
            requirement.save(update_fields=["parsed_text"])
            # 抽取的图片同步入库为原型图/UI 图（AI 按「端-模块名-功能名-用途」取名）
            prototype_created = 0
            if images:
                try:
                    prototype_created = _save_images_as_prototypes(requirement, text, images, request.user)
                except Exception as e:
                    # 取名/入库失败不影响文档上传
                    logger.warning("[图片入库] 文档图片入库原型图库失败：%s", e)
        else:
            prototype_created = 0
            try:
                parsed_text = document_parser.parse_file(file_path)
            except ValueError as e:
                requirement.delete()
                return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
            requirement.parsed_text = parsed_text
            requirement.save(update_fields=["parsed_text"])

        payload = RequirementSerializer(requirement).data
        payload["prototype_images_created"] = prototype_created
        return Response(payload, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="analyze")
    def analyze(self, request, pk=None):
        """调用 AI 进行需求完整度检测。"""
        requirement = self.get_object()
        if not requirement.parsed_text:
            return Response({"detail": "该需求文档无有效内容，请重新上传"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = analyze_requirement(requirement.parsed_text)
        except Exception as e:  # LLM 调用失败等
            return Response({"detail": f"AI 分析失败：{e}"}, status=status.HTTP_502_BAD_GATEWAY)
        requirement.analysis_result = result
        requirement.save(update_fields=["analysis_result"])
        return Response(RequirementSerializer(requirement).data)

    @action(detail=True, methods=["post"], url_path="confirm")
    def confirm(self, request, pk=None):
        """确认需求无误：初始化项目知识入库，项目进入开发阶段。"""
        requirement = self.get_object()
        if not requirement.analysis_result:
            return Response({"detail": "请先执行 AI 分析"}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            requirement.is_confirmed = True
            requirement.save(update_fields=["is_confirmed"])
            # 初始化项目知识：解析文本切块 + 写入向量库
            chunks = document_parser.chunk_text(requirement.parsed_text)
            metadatas = [
                {"source": requirement.title, "type": "requirement", "requirement_id": requirement.id}
                for _ in chunks
            ]
            ids = [f"req{requirement.id}_c{i}" for i in range(len(chunks))]
            vector_store.add_knowledge(requirement.project_id, chunks, metadatas, ids)
            # 项目进入「项目计划」阶段
            project = requirement.project
            if project.status == "requirement":
                project.status = "planning"
                project.save(update_fields=["status"])

        return Response(RequirementSerializer(requirement).data)


class PrototypeImagePagination(PageNumberPagination):
    """原型图列表分页（默认每页 12，支持 ?page_size= 覆盖，上限 100）。"""
    page_size = 12
    page_size_query_param = "page_size"
    max_page_size = 100


class PrototypeImageViewSet(viewsets.ModelViewSet):
    """原型图 / UI 图管理（客户上传，按项目隔离）。"""

    queryset = PrototypeImage.objects.select_related("project", "uploader").all()
    serializer_class = PrototypeImageSerializer
    pagination_class = PrototypeImagePagination
    http_method_names = ["get", "post", "patch", "delete"]

    def get_queryset(self):
        qs = self.queryset
        project_id = self.request.query_params.get("project_id")
        if project_id:
            qs = qs.filter(project_id=project_id)
        kind = self.request.query_params.get("kind")
        if kind:
            qs = qs.filter(kind=kind)
        name = (self.request.query_params.get("name") or "").strip()
        if name:
            qs = qs.filter(name__icontains=name)
        # 稳定排序：同秒创建时再按 id 倒序，保证分页不重不漏
        return qs.order_by("-created_at", "-id")

    @action(detail=False, methods=["post"], url_path="batch-delete")
    def batch_delete(self, request):
        """批量删除图片：仅删除当前筛选项目（project_id）范围内的图片，并清理物理文件。"""
        user = request.user
        is_admin = bool(user and (user.is_superuser or getattr(user, "role", None) == "admin"))
        project_id = request.query_params.get("project_id") or request.data.get("project_id")
        # 非管理员必须限定项目，否则会越过项目隔离删到其它项目的图
        if not is_admin and not project_id:
            return Response({"detail": "缺少 project_id"}, status=status.HTTP_400_BAD_REQUEST)
        ids = request.data.get("ids") or []
        if not isinstance(ids, list) or not ids:
            return Response({"detail": "ids 不能为空"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            ids = [int(i) for i in ids]
        except (TypeError, ValueError):
            return Response({"detail": "ids 必须是图片 id 列表"}, status=status.HTTP_400_BAD_REQUEST)
        qs = self.get_queryset().filter(id__in=ids)
        deleted = 0
        for obj in qs:
            if obj.image and obj.image.name:
                obj.image.delete(save=False)  # 清理物理文件
            obj.delete()
            deleted += 1
        return Response({"deleted": deleted})

    def create(self, request, *args, **kwargs):
        # 支持远程 URL 上传（MCP/AI agent 无法直接传二进制文件，可提供图片 URL）
        data = request.data.copy()
        if not request.FILES.get("image") and data.get("image_url"):
            from django.core.files.base import ContentFile

            import requests as _requests

            url = data.pop("image_url")
            try:
                resp = _requests.get(url, timeout=30)
                resp.raise_for_status()
            except Exception:
                return Response({"detail": "图片 URL 拉取失败，请确认地址可访问"}, status=status.HTTP_400_BAD_REQUEST)
            if not resp.headers.get("Content-Type", "").startswith("image/"):
                return Response({"detail": "该 URL 不是图片资源"}, status=status.HTTP_400_BAD_REQUEST)
            filename = (url.split("/")[-1].split("?")[0] or "image.png")
            data["image"] = ContentFile(resp.content, name=filename)

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        try:
            self.perform_create(serializer)
        except IntegrityError:
            # 图名称在项目内唯一，重名给出友好提示
            return Response(
                {"detail": f"图名称「{data.get('name', '')}」已存在，请换一个名称"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        serializer.save(uploader=self.request.user if self.request.user.is_authenticated else None)

    def update(self, request, *args, **kwargs):
        """编辑图名称/类型；重名时给出友好提示（project+name 唯一）。"""
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        try:
            self.perform_update(serializer)
        except IntegrityError:
            return Response(
                {"detail": f"图名称「{request.data.get('name', '')}」在该项目已存在，请换一个名称"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.image and obj.image.name:
            obj.image.delete(save=False)  # 清理物理文件
        self.perform_destroy(obj)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"], url_path="download")
    def download(self, request, pk=None):
        """下载图片原始字节（供 MCP/AI agent 拉取图片内容）。"""
        import mimetypes
        from urllib.parse import quote

        from django.http import FileResponse

        obj = self.get_object()
        if not obj.image or not obj.image.name:
            return Response({"detail": "图片文件不存在"}, status=status.HTTP_404_NOT_FOUND)
        resp = FileResponse(obj.image.open("rb"))
        resp["Content-Type"] = mimetypes.guess_type(obj.image.name)[0] or "application/octet-stream"
        # RFC 5987：中文文件名用 filename*=UTF-8'' 编码，避免乱码/截断
        filename = obj.image.name.split("/")[-1]
        resp["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(filename)}"
        return resp
