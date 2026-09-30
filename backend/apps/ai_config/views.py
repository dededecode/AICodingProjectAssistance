from rest_framework import permissions, status, views
from rest_framework.response import Response
from django.utils import timezone

from apps.rbac.permissions import ApiResourcePermission
from services import embedding, llm
from .models import AiConfig, EmbeddingCallLog, UserAiConfig
from .serializers import AiTestSerializer, EmbeddingConfigSerializer, UserAiConfigSerializer


def _is_admin(user):
    return user.is_superuser or user.role == "admin"


class AiConfigView(views.APIView):
    """当前登录用户自己的 LLM/Vision 配置 + 全局共享 Embedding 配置。

    安全：只读写 request.user 自己的配置，不接受 user_id，杜绝读取他人 Key。
    Embedding 为全局共享，仅管理员可修改。
    """

    permission_classes = [permissions.IsAuthenticated, ApiResourcePermission]

    def get(self, request):
        ucfg = getattr(request.user, "ai_config", None)
        gcfg = AiConfig.load()
        return Response(
            {
                "user": UserAiConfigSerializer(ucfg).data if ucfg else None,
                "embedding": EmbeddingConfigSerializer(gcfg).data,
            }
        )

    def put(self, request):
        # 1) 当前用户自己的 LLM/Vision 配置
        ucfg, _ = UserAiConfig.objects.get_or_create(user=request.user)
        user_ser = UserAiConfigSerializer(ucfg, data=request.data.get("user") or {}, partial=True)
        user_ser.is_valid(raise_exception=True)
        user_ser.save()

        # 2) 全局 Embedding 配置（仅管理员）
        embedding_data = request.data.get("embedding")
        if embedding_data is not None:
            if not _is_admin(request.user):
                return Response(
                    {"detail": "嵌入模型配置为全局共享，仅管理员可修改"},
                    status=status.HTTP_403_FORBIDDEN,
                )
            gcfg = AiConfig.load()
            emb_ser = EmbeddingConfigSerializer(gcfg, data=embedding_data, partial=True)
            emb_ser.is_valid(raise_exception=True)
            emb_ser.save()

        return self.get(request)


class EmbeddingLogView(views.APIView):
    """嵌入模型调用日志（仅管理员）：分页返回调用时间、调用账号。"""

    permission_classes = [permissions.IsAuthenticated, ApiResourcePermission]

    def get(self, request):
        if not _is_admin(request.user):
            return Response({"detail": "仅管理员可查看日志"}, status=status.HTTP_403_FORBIDDEN)
        try:
            page = max(1, int(request.query_params.get("page", 1)))
            page_size = min(max(1, int(request.query_params.get("page_size", 20))), 100)
        except (TypeError, ValueError):
            page, page_size = 1, 20
        qs = EmbeddingCallLog.objects.all().order_by("-called_at")
        total = qs.count()
        start = (page - 1) * page_size
        items = qs[start : start + page_size]
        return Response(
            {
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": [
                    {"id": log.id, "username": log.username or "-", "called_at": timezone.localtime(log.called_at).strftime("%Y-%m-%d %H:%M:%S")}
                    for log in items
                ],
            }
        )


class AiTestView(views.APIView):
    """测试当前用户配置的模型连接（LLM/Vision 用当前用户 key，Embedding 用全局配置）。"""

    permission_classes = [permissions.IsAuthenticated, ApiResourcePermission]

    def post(self, request):
        serializer = AiTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        kind = serializer.validated_data["kind"]
        try:
            if kind == "llm":
                resp = llm.chat(
                    [{"role": "user", "content": "请只回复：连接成功"}],
                    max_tokens=16,
                )
                return Response({"ok": True, "message": f"LLM 连接成功，模型返回：{resp[:50]}"})
            elif kind == "vision":
                from services import vision

                # 用一张 1x1 透明 PNG 做连通性测试
                tiny_png = (
                    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
                    "+A8AAQUBAScY42YAAAAASUVORK5CYII="
                )
                import base64 as _b64
                import os
                import tempfile

                tmp = os.path.join(tempfile.gettempdir(), "vision_test.png")
                with open(tmp, "wb") as f:
                    f.write(_b64.b64decode(tiny_png))
                desc = vision.describe_image(tmp, "请回复：视觉OK")
                return Response({"ok": True, "message": f"多模态模型连接成功，返回：{desc[:50]}"})
            else:
                from services.embedding import embed_texts

                embed_texts(["测试"])
                return Response({"ok": True, "message": "Embedding 连接/加载成功"})
        except Exception as e:
            return Response(
                {"ok": False, "message": f"测试失败：{e}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )
