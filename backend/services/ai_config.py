"""模型配置读取：
- LLM / Vision：每个用户各自的配置优先（UserAiConfig），未配置回退环境变量兜底。
- Embedding：全局共享配置（AiConfig 单行），对全体用户一致，避免向量库混乱；
  远程 API Key 解析链：当前用户配置 → admin 用户配置 → 环境变量兜底。
"""

from django.conf import settings

from .current_user import get_current_user
from .db_crypto import dec


def _user_cfg():
    """返回当前请求用户自己的配置对象；无请求上下文时返回 None。"""
    user = get_current_user()
    if user and user.is_authenticated:
        return getattr(user, "ai_config", None)
    return None


def _val(user_value, env_value):
    """字段取值：用户配置非空用用户值，否则环境变量兜底。"""
    return (user_value or "").strip() or env_value


def _admin_user():
    """内置 admin 账号（key 兜底来源）。"""
    from apps.accounts.models import User

    return User.objects.filter(username="admin").first()


def get_llm_config():
    ucfg = _user_cfg()
    return {
        "base_url": _val(getattr(ucfg, "llm_base_url", None) if ucfg else None, settings.LLM_BASE_URL),
        "api_key": dec(_val(getattr(ucfg, "llm_api_key", None) if ucfg else None, settings.LLM_API_KEY)),
        "model": _val(getattr(ucfg, "llm_model", None) if ucfg else None, settings.LLM_MODEL),
    }


def get_embedding_api_key():
    """解析远程 embedding 的 API Key 及归属账号。

    解析链：当前用户 LLM Key → admin 用户 LLM Key → 环境变量兜底。
    返回 (api_key, account)，account 用于调用日志记录实际使用方。
    """
    ucfg = _user_cfg()
    if ucfg and (ucfg.llm_api_key or "").strip():
        user = get_current_user()
        return dec(ucfg.llm_api_key.strip()), (user.username if user else "user")
    admin = _admin_user()
    if admin:
        acfg = getattr(admin, "ai_config", None)
        if acfg and (acfg.llm_api_key or "").strip():
            return dec(acfg.llm_api_key.strip()), admin.username
    return (settings.LLM_API_KEY or "").strip(), "env"


def get_vision_config():
    ucfg = _user_cfg()
    return {
        "base_url": _val(getattr(ucfg, "vision_base_url", None) if ucfg else None, settings.VISION_BASE_URL),
        "api_key": dec(_val(getattr(ucfg, "vision_api_key", None) if ucfg else None, settings.VISION_API_KEY)),
        "model": _val(getattr(ucfg, "vision_model", None) if ucfg else None, settings.VISION_MODEL),
    }


def get_embedding_config():
    from apps.ai_config.models import AiConfig

    cfg = AiConfig.load()
    return {
        "mode": cfg.embedding_mode or settings.EMBEDDING_MODE,
        "model": cfg.embedding_model or settings.EMBEDDING_MODEL,
        "remote_base_url": cfg.llm_embedding_base_url or settings.LLM_EMBEDDING_BASE_URL,
        "remote_model": cfg.llm_embedding_model or settings.LLM_EMBEDDING_MODEL,
    }
