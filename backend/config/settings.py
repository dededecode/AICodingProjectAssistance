"""
Django settings for the AI Project Management Platform backend.
"""
import os
from datetime import timedelta
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-dev-only-change-me")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"

ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "*").split(",")

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # third-party
    "rest_framework",
    "corsheaders",
    # local apps
    "apps.accounts",
    "apps.projects",
    "apps.requirements",
    "apps.knowledge",
    "apps.collaboration",
    "apps.testing",
    "apps.delivery",
    "apps.ai_config",
    "apps.project_planning",
    "apps.architecture",
    "apps.operation",
    "apps.wiki",
    "apps.rbac",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.accounts.middleware.CurrentUserMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Database — SQLite（路径可用环境变量覆盖，便于 Docker 挂载持久化）
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.getenv("DB_PATH", str(BASE_DIR / "db.sqlite3")),
    }
}

# Custom user model
AUTH_USER_MODEL = "accounts.User"

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Internationalization
LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True

# Static / Media files（路径可用环境变量覆盖，便于 Docker 挂载持久化）
STATIC_URL = "static/"
STATIC_ROOT = os.getenv("STATIC_ROOT", str(BASE_DIR / "staticfiles"))
MEDIA_URL = "/media/"
MEDIA_ROOT = os.getenv("MEDIA_ROOT", str(BASE_DIR / "media"))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ─── Django REST Framework ───
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "apps.accounts.auth.ContextAwareAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
        "apps.accounts.permissions.IsProjectMemberOrAdmin",
    ),
    "DEFAULT_RENDERER_CLASSES": (
        "rest_framework.renderers.JSONRenderer",
    ),
}

# 服务令牌：供本地其他编程 agent（MCP 等）无需登录调用 API，请修改为自定义值
SERVICE_TOKEN = os.getenv("PLATFORM_SERVICE_TOKEN", "local-mcp-service-token")

# ─── 生产模式安全自检：拒绝带着开发默认值上线 ───
# 这两个默认值一旦用于生产，等同于公开了签名密钥与一个管理员级服务令牌。
if not DEBUG:
    _insecure = []
    if SECRET_KEY == "django-insecure-dev-only-change-me":
        _insecure.append("DJANGO_SECRET_KEY")
    if SERVICE_TOKEN == "local-mcp-service-token":
        _insecure.append("PLATFORM_SERVICE_TOKEN")
    if _insecure:
        from django.core.exceptions import ImproperlyConfigured

        raise ImproperlyConfigured(
            "DEBUG=0 时禁止使用开发默认值，请先设置环境变量：" + "、".join(_insecure)
        )

# ─── JWT (simplejwt) ───
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=2),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# ─── CORS ───
CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOW_CREDENTIALS = True

# ─── AI / LLM（OpenAI 兼容协议） ───
# 需求分析与文档生成共用同一套 OpenAI 兼容配置。
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")

# 多模态 LLM（vision，用于图文文档图片解析），未单独配置时回退到 LLM 配置
VISION_BASE_URL = os.getenv("VISION_BASE_URL", LLM_BASE_URL)
VISION_API_KEY = os.getenv("VISION_API_KEY", LLM_API_KEY)
VISION_MODEL = os.getenv("VISION_MODEL", LLM_MODEL)

# ─── Embedding ───
# EMBEDDING_MODE: "local"（默认，sentence-transformers bge-small-zh）| "remote"（OpenAI 兼容 embedding 端点）
EMBEDDING_MODE = os.getenv("EMBEDDING_MODE", "local")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
# remote 模式下的 embedding 端点与模型（如 Ollama: http://localhost:11434/v1 + nomic-embed-text）
LLM_EMBEDDING_BASE_URL = os.getenv("LLM_EMBEDDING_BASE_URL", LLM_BASE_URL)
LLM_EMBEDDING_MODEL = os.getenv("LLM_EMBEDDING_MODEL", "nomic-embed-text")

# 远程 embedding 单次批量大小（部分端点限制单次输入条数）
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "8"))

# Chroma 向量库持久化目录
CHROMA_DIR = os.getenv("CHROMA_DIR", str(BASE_DIR / "chroma"))

# ─── 日志：应用/服务 INFO 输出到控制台，便于排查 AI 生成等耗时流程 ───
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "[%(asctime)s] %(levelname)s %(name)s: %(message)s", "datefmt": "%H:%M:%S"}
    },
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "simple"}},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO"},
        "apps": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "services": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
