from django.conf import settings
from django.db import models


class ProjectPlan(models.Model):
    """项目计划（AI 生成）。"""

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="plans"
    )
    name = models.CharField("计划名称", max_length=200)
    requirement = models.ForeignKey(
        "requirements.Requirement",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="plans",
        verbose_name="依据需求文档",
    )
    planned_members = models.PositiveIntegerField("计划人数")
    start_date = models.DateField("计划开始时间")
    launch_date = models.DateField("计划上线时间")
    plan_content = models.TextField("计划内容(markdown)")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "项目计划"
        verbose_name_plural = "项目计划"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.project.name} - {self.name}"


class ProjectPlanMember(models.Model):
    """计划成员及其开发工作权重（占比）。"""

    plan = models.ForeignKey(ProjectPlan, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="plan_memberships"
    )
    weight = models.FloatField("开发工作占比(0-1)", default=0.0)

    class Meta:
        verbose_name = "计划成员"
        verbose_name_plural = "计划成员"
        unique_together = ("plan", "user")

    def __str__(self):
        return f"{self.user.username} {self.weight}"


class PlanTask(models.Model):
    """计划生成的结构化开发任务，指派到人。"""

    DIFFICULTY_CHOICES = [
        ("simple", "简单"),
        ("medium", "中等"),
        ("hard", "复杂"),
    ]
    STATUS_CHOICES = [
        ("pending", "待执行"),
        ("executing", "执行中"),
        ("done", "已完成"),
        ("blocked", "阻塞"),
    ]

    plan = models.ForeignKey(ProjectPlan, on_delete=models.CASCADE, related_name="tasks", null=True, blank=True)
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="plan_tasks"
    )
    title = models.CharField("任务名称", max_length=300)
    description = models.TextField("任务描述", blank=True, default="")
    module = models.CharField("业务模块", max_length=200, blank=True, default="")
    difficulty = models.CharField("难度", max_length=20, choices=DIFFICULTY_CHOICES, default="medium")
    estimated_days = models.FloatField("预估工期(人日)", default=0)
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="plan_tasks"
    )
    status = models.CharField("状态", max_length=20, choices=STATUS_CHOICES, default="pending")
    start_date = models.DateField("计划开始", null=True, blank=True)
    end_date = models.DateField("计划完成", null=True, blank=True)
    depends = models.CharField("前置依赖", max_length=300, blank=True, default="")
    ui_images = models.JSONField("关联原型图/UI图名称列表", default=list, blank=True)
    sort_order = models.PositiveIntegerField("排序", default=0)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "开发任务"
        verbose_name_plural = "开发任务"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.title
