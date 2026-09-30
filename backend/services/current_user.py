"""当前请求用户的线程上下文。

DRF 认证通过后，把当前用户写入线程局部变量，供服务层（LLM/Vision 等）
按用户解析各自的模型配置。请求结束由中间件清理，避免多线程/多用户串号。
"""
import threading

_ctx = threading.local()


def set_current_user(user):
    _ctx.user = user


def get_current_user():
    return getattr(_ctx, "user", None)


def clear_current_user():
    _ctx.user = None
