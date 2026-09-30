from django.conf import settings
from django.db import models

BASE_FRAMEWORK_CHOICES = [
    ("", "无（自研）"),
    ("ruoyi-vue-plus", "Ruoyi-Vue-Plus（5.x）"),
    ("smart-admin", "Smart-Admin"),
]
DB_TYPE_CHOICES = [
    ("mysql", "MySQL"),
    ("postgresql", "PostgreSQL"),
]


class ArchitectureDesign(models.Model):
    """项目架构设计（架构概设文档 + 数据库设计）。"""

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="arch_designs"
    )
    frontend_stack = models.CharField("前端技术栈", max_length=200)
    backend_stack = models.CharField("后端技术栈", max_length=200)
    base_framework = models.CharField("框架底座", max_length=50, choices=BASE_FRAMEWORK_CHOICES, default="", blank=True)
    db_type = models.CharField("数据库类型", max_length=20, choices=DB_TYPE_CHOICES, default="mysql")
    design_doc = models.TextField("架构概设文档(markdown)", blank=True, default="")
    db_sql = models.TextField("数据库设计 SQL", blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "架构设计"
        verbose_name_plural = "架构设计"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.project.name} 架构设计"


class ArchitectureChat(models.Model):
    """架构设计 AI 对话历史（每个设计一条线程，支持多轮）。"""

    design = models.OneToOneField(ArchitectureDesign, on_delete=models.CASCADE, related_name="chat_thread")
    messages = models.JSONField("对话消息", default=list)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "架构设计对话"
        verbose_name_plural = "架构设计对话"

    def __str__(self):
        return f"对话-{self.design_id}"
