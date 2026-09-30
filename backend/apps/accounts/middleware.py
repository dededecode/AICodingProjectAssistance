"""清理当前请求用户线程上下文，防止多用户/多线程串号。

普通响应：响应返回后立即清理；
流式响应（SSE）：响应体在 close 时才真正生成完毕，故包装 close 在流结束后清理。
"""
from services import current_user


class CurrentUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if getattr(response, "streaming", False):
            old_close = response.close

            def close():
                try:
                    current_user.clear_current_user()
                finally:
                    old_close()

            response.close = close
        else:
            current_user.clear_current_user()
        return response
