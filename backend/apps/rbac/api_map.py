"""API 路径 → 权限组资源码映射（全接口白名单，真授权）。

约定：
  - 管理员/超管（role=admin 或 is_superuser）放行全部接口；
  - PUBLIC：无需登录（视图自身 AllowAny 处理）；
  - AUTH_ANY：登录即可访问，不绑定资源码（个人/基础接口）；
  - RESOURCE：按前缀映射到资源码（与前端菜单同码联动——勾选菜单即授权该模块接口），
    用户权限组勾选该码才放行，否则 403；
  - 未匹配到任何前缀的路径默认放行（当前全部 /api/ 接口已显式映射，防误伤兜底）。

映射与前端菜单资源码一一对应：
  projects→需求分析  prototype-images→原型图  project-plans→项目计划  plan-tasks→任务管理
  architecture→架构设计  test-*|bugs→测试管理  knowledge→知识库
  wiki→Wiki知识库  work-logs|weekly-summaries→工时登记  work-groups→工作群
  operation-*→运营管理  delivery-docs→交付文档  admin-users→用户管理
  ai-config→模型管理  rbac→权限组管理
"""

# 功能下线屏蔽：命中即 403（含 admin）。当前无下线功能，保留机制备用。
DENY_PREFIXES = ()

# 登录即可访问、不绑定资源码的路径（已归一化、无尾斜杠）
AUTH_ANY = (
    "/api/auth/me",
    "/api/auth/change-password",
    "/api/auth/users",  # 用户搜索（项目邀请/工作群选人用，仅返回 id/用户名/角色）
    "/api/rbac/my-resources",
    "/api/work-logs/dashboard",  # 首页统计（首页始终可见）
)

# 前缀 → 资源码（顺序敏感：具体前缀在前，避免被宽前缀抢先匹配）
MAP = (
    ("/api/auth/admin-users", "menu:users"),
    ("/api/rbac", "menu:rbac"),
    ("/api/ai-config/embedding-logs", "menu:embedding-logs"),
    ("/api/ai-config", "menu:model-config"),
    ("/api/requirements", "menu:projects"),
    ("/api/prototype-images", "menu:prototype-images"),
    ("/api/project-plans", "menu:project-planning"),
    ("/api/plan-tasks", "menu:tasks"),
    ("/api/architecture", "menu:architecture"),
    ("/api/test-cases", "menu:testing"),
    ("/api/test-tasks", "menu:testing"),
    ("/api/bugs", "menu:testing"),
    ("/api/knowledge", "menu:knowledge"),
    ("/api/wiki", "menu:llm-wiki"),
    ("/api/delivery-docs", "menu:delivery-docs"),
    ("/api/work-logs", "menu:collaboration"),
    ("/api/weekly-summaries", "menu:collaboration"),
    ("/api/work-groups", "menu:work-groups"),
    ("/api/operation-items", "menu:operation"),
    ("/api/operation-metrics", "menu:operation"),
    ("/api/projects", "menu:projects"),
)


def _norm(path):
    p = (path or "").split("?", 1)[0]
    if len(p) > 1:
        p = p.rstrip("/")
    return p


def resolve_resource(path, method):
    """解析路径对应的资源码。

    返回 (mode, code)：mode ∈ {"public", "any", "resource", "deny"}；resource 模式下 code 为资源码。
    """
    p = _norm(path)
    if p in ("/api/auth/captcha", "/api/auth/login", "/api/auth/rsa-public-key", "/api/auth/refresh"):
        return "public", None
    if p in AUTH_ANY:
        return "any", None
    for prefix in DENY_PREFIXES:
        if p == prefix or p.startswith(prefix + "/"):
            return "deny", None
    # 项目列表按成员过滤，被多个模块页面共用作选择器 → GET 登录即可；其它方法（创建）需 menu:projects
    if p == "/api/projects":
        if (method or "GET").upper() == "GET":
            return "any", None
        return "resource", "menu:projects"
    for prefix, code in MAP:
        if p == prefix or p.startswith(prefix + "/"):
            return "resource", code
    return "any", None  # 未映射兜底放行（全部已知接口均已显式映射）


def check_api_access(user, path, method):
    """校验用户是否可访问该 API 路径。返回 (allowed, code)。

    allowed=False 时 code 为缺失的资源码（用于 403 提示）；any/public 模式 code=None。
    deny 模式（功能下线）对包括 admin 在内的所有用户一律拒绝。
    """
    if not user or not user.is_authenticated:
        return False, None
    if not _norm(path).startswith("/api/"):
        return True, None
    mode, code = resolve_resource(path, method)
    if mode == "deny":
        return False, None
    if user.is_superuser or getattr(user, "role", "") == "admin":
        return True, None
    if mode in ("public", "any"):
        return True, None
    from .services import user_allowed_codes

    if code in user_allowed_codes(user):
        return True, code
    return False, code
