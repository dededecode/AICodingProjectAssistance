from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import User
from .serializers import (
    ChangePasswordSerializer,
    LoginSerializer,
    UserManageSerializer,
    UserSerializer,
)


class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_superuser or request.user.role == "admin"


class AdminUserViewSet(viewsets.ModelViewSet):
    """用户管理（仅管理员）。"""

    queryset = User.objects.all().order_by("id")
    serializer_class = UserManageSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    http_method_names = ["get", "post", "patch", "delete"]

    def _is_protected(self, user):
        """系统账号保护：超级管理员或内置 admin 账号不允许删除/修改。"""
        return user.is_superuser or user.username == "admin"

    def _forbid_protected(self, user, action):
        if self._is_protected(user):
            return Response({"detail": f"系统账号「{user.username}」不允许{action}"}, status=status.HTTP_400_BAD_REQUEST)
        return None

    def update(self, request, *args, **kwargs):
        user = self.get_object()
        blocked = self._forbid_protected(user, "修改")
        if blocked:
            return blocked
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        user = self.get_object()
        blocked = self._forbid_protected(user, "修改")
        if blocked:
            return blocked
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        blocked = self._forbid_protected(user, "删除")
        if blocked:
            return blocked
        if user.id == request.user.id:
            return Response({"detail": "不能删除当前登录账号"}, status=status.HTTP_400_BAD_REQUEST)
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="reset-password")
    def reset_password(self, request, pk=None):
        user = self.get_object()
        blocked = self._forbid_protected(user, "重置密码")
        if blocked:
            return blocked
        new_password = request.data.get("new_password")
        if not new_password or len(new_password) < 6:
            return Response({"detail": "新密码至少 6 位"}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(new_password)
        user.save(update_fields=["password"])
        return Response({"detail": "密码已重置"})

    @action(detail=True, methods=["post"], url_path="regenerate-token")
    def regenerate_token(self, request, pk=None):
        """重新生成用户的 MCP Token（旧令牌立即失效）。"""
        user = self.get_object()
        blocked = self._forbid_protected(user, "重新生成 MCP Token")
        if blocked:
            return blocked
        from .models import _gen_mcp_token

        user.mcp_token = _gen_mcp_token()
        user.save(update_fields=["mcp_token"])
        return Response({"mcp_token": user.mcp_token})


class ChangePasswordView(APIView):
    """修改当前用户密码。"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = request.user
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])
        return Response({"detail": "密码修改成功"})


class UserListView(APIView):
    """用户列表（用于邀请成员选择）。"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        keyword = request.query_params.get("search", "").strip()
        qs = User.objects.all()
        if keyword:
            qs = qs.filter(username__icontains=keyword)
        return Response(UserSerializer(qs, many=True).data)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = {
            "refresh": serializer.validated_data["refresh"],
            "access": serializer.validated_data["access"],
            "user": UserSerializer(serializer.validated_data["user"]).data,
        }
        return Response(data)


class CaptchaView(APIView):
    """获取登录图形验证码（图片 base64 + captcha_id）。"""

    permission_classes = [AllowAny]

    def get(self, request):
        from .captcha import generate_captcha

        return Response(generate_captcha())


class RsaPublicKeyView(APIView):
    """获取登录 RSA 公钥（PEM）。"""

    permission_classes = [AllowAny]

    def get(self, request):
        from .rsa_crypto import get_public_key_pem

        return Response({"public_key": get_public_key_pem()})


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)
