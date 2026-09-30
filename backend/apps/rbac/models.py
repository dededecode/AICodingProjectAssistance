from django.contrib.auth.models import Group
from django.db import models

# 内置角色：与 accounts.User.role 一一对应，作为 RBAC 的初始 Group
BUILTIN_ROLES = ["admin", "manager", "developer", "tester", "guest"]


class RoleResource(models.Model):
    """角色(Group) ↔ 资源码授权关系。

    资源码分三类：
      menu:*  前端菜单
      btn:*   前端按钮
      api:*   后端接口
    某资源码只要被任一角色配置过即视为「已启用」；已启用的资源码按本表判定，
    未启用的资源码由调用方按原有 role 硬编码逻辑兜底（平滑演进、零回归）。
    """

    TYPE_CHOICES = [
        ("menu", "菜单"),
        ("btn", "按钮"),
        ("api", "接口"),
    ]

    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="rbac_resources")
    code = models.CharField("资源码", max_length=100)
    resource_type = models.CharField("资源类型", max_length=20, choices=TYPE_CHOICES)

    class Meta:
        verbose_name = "角色资源"
        verbose_name_plural = "角色资源"
        unique_together = ("group", "code")

    def __str__(self):
        return f"{self.group.name} -> {self.code}"
