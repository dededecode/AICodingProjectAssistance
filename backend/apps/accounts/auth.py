"""服务令牌认证：供本地其他编程 agent（MCP 等）无需登录即可调用 API。

客户端请求头携带 `Authorization: Bearer <token>`：
- 全局服务令牌（settings.SERVICE_TOKEN，兼容旧配置）→ 对应固定的服务用户（admin 角色）
- 某用户的 mcp_token → 认证为该真实用户（用于按用户区分权限，如项目成员校验）
与普通 JWT 登录并存。
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.authentication import BaseAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication


class ServiceTokenAuthentication(BaseAuthentication):
    def authenticate(self, request):
        auth = request.headers.get("Authorization", "")
        token = ""
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
        if not token:
            return None

        # 1) 全局服务令牌（兼容旧配置）→ 固定的服务用户
        if token == getattr(settings, "SERVICE_TOKEN", ""):
            User = get_user_model()
            user, created = User.objects.get_or_create(
                username="mcp", defaults={"is_staff": True, "role": "admin"}
            )
            if not created and user.role != "admin":
                # get_or_create 的 defaults 只在首次创建生效，历史遗留用户在此校正角色
                user.role = "admin"
                user.save(update_fields=["role"])
            return (user, None)

        # 2) 用户 MCP Token → 对应真实用户（区分用户；已禁用账号不通过）
        User = get_user_model()
        try:
            user = User.objects.get(mcp_token=token)
        except User.DoesNotExist:
            return None  # 未匹配则交由后续认证（JWT）处理
        if not user.is_active:
            return None
        return (user, None)

    def authenticate_header(self, request):
        return "Bearer"


class ContextAwareAuthentication(BaseAuthentication):
    """统一认证入口：依次尝试【服务令牌 → JWT】，并把认证出的当前用户写入线程上下文，
    供服务层（LLM/Vision）按用户取各自的模型配置（不会跨用户串号）。"""

    def __init__(self):
        self._service = ServiceTokenAuthentication()
        self._jwt = JWTAuthentication()

    def authenticate(self, request):
        from services import current_user

        for auth in (self._service, self._jwt):
            result = auth.authenticate(request)
            if result is not None:
                current_user.set_current_user(result[0])
                return result
        return None

    def authenticate_header(self, request):
        return "Bearer"
