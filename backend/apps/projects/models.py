from django.conf import settings
from django.db import models


class Project(models.Model):
    """项目。"""

    STATUS_CHOICES = [
        ("requirement", "需求分析"),
        ("planning", "项目计划"),
        ("architecture", "架构设计"),
        ("developing", "开发实施"),
        ("delivery", "项目交付"),
        ("operation", "项目运营"),
    ]

    name = models.CharField("项目名称", max_length=200)
    description = models.TextField("项目描述", blank=True, default="")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_projects",
        verbose_name="负责人",
    )
    status = models.CharField(
        "状态", max_length=20, choices=STATUS_CHOICES, default="requirement"
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="ProjectMember",
        related_name="projects",
        verbose_name="成员",
    )

    class Meta:
        verbose_name = "项目"
        verbose_name_plural = "项目"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class ProjectMember(models.Model):
    """项目-成员关联（含成员在项目中的角色）。"""

    ROLE_CHOICES = [
        ("manager", "项目经理"),
        ("developer", "开发"),
        ("tester", "测试"),
        ("guest", "访客"),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="member_links")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="project_memberships"
    )
    role = models.CharField("成员角色", max_length=20, choices=ROLE_CHOICES, default="developer")
    joined_at = models.DateTimeField("加入时间", auto_now_add=True)

    class Meta:
        verbose_name = "项目成员"
        verbose_name_plural = "项目成员"
        unique_together = ("project", "user")

    def __str__(self):
        return f"{self.project.name} - {self.user.username}"
