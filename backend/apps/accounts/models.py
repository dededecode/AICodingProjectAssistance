from django.contrib.auth.models import AbstractUser
from django.db import models

ROLE_CHOICES = [
    ("admin", "管理员"),
    ("manager", "项目经理"),
    ("developer", "开发"),
    ("tester", "测试"),
    ("guest", "访客"),
]


def _gen_mcp_token():
    """生成随机的 MCP 通信令牌。"""
    import secrets

    return "mcp-" + secrets.token_urlsafe(24)


class User(AbstractUser):
    """平台用户，带角色字段。"""

    role = models.CharField("角色", max_length=20, choices=ROLE_CHOICES, default="developer")
    name = models.CharField("姓名", max_length=50, blank=True, default="")
    capability = models.TextField("人员能力描述", blank=True, default="", help_text="用于 AI 生成项目计划时参考，如擅长技术栈、可承担职责等")
    mcp_token = models.CharField("MCP Token", max_length=64, unique=True, blank=True, default="", help_text="MCP 与平台接口通信的令牌，标识该用户身份")

    class Meta:
        verbose_name = "用户"
        verbose_name_plural = "用户"

    def __str__(self):
        return self.username

    def save(self, *args, **kwargs):
        # 新增用户时自动生成 MCP Token（空值回填）
        if not self.mcp_token:
            self.mcp_token = _gen_mcp_token()
        super().save(*args, **kwargs)


class LoginCaptcha(models.Model):
    """登录图形验证码（一次性，JWT 无 session，用 DB 表存储）。"""

    code = models.CharField("验证码", max_length=8)
    expires_at = models.DateTimeField("过期时间")
    used = models.BooleanField("是否已使用", default=False)
    fail_count = models.IntegerField("连续失败次数", default=0)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "登录验证码"
        verbose_name_plural = "登录验证码"

    def __str__(self):
        return f"{self.code} ({self.expires_at:%m-%d %H:%M})"
