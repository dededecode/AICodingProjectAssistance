from django.conf import settings
from django.db import models


class WorkLog(models.Model):
    """工时登记。"""

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="work_logs"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="work_logs"
    )
    date = models.DateField("日期")
    hours = models.DecimalField("工时(小时)", max_digits=5, decimal_places=2)
    description = models.CharField("工作内容", max_length=500, blank=True, default="")
    tasks = models.ManyToManyField(
        "project_planning.PlanTask", blank=True, related_name="work_logs", verbose_name="关联任务"
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "工时登记"
        verbose_name_plural = "工时登记"
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"{self.user.username} {self.date} {self.hours}h"


class WeeklySummary(models.Model):
    """周总结。"""

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="weekly_summaries"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="weekly_summaries"
    )
    week_start = models.DateField("周起始日")
    content = models.TextField("周总结内容")
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "周总结"
        verbose_name_plural = "周总结"
        ordering = ["-week_start"]
        unique_together = ("project", "user", "week_start")

    def __str__(self):
        return f"{self.user.username} 周总结 {self.week_start}"


class WorkGroup(models.Model):
    """工作群（多 agent 协作群聊，当前由用户手动切换身份发言模拟 agent）。"""

    STATUS_CHOICES = [
        ("active", "活跃"),
        ("dismissed", "已解散"),
    ]

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="work_groups"
    )
    name = models.CharField("群名称", max_length=200)
    status = models.CharField("群状态", max_length=20, choices=STATUS_CHOICES, default="active")
    workflow_desc = models.TextField("工作流程定义", blank=True, default="")
    dev_task_prompt = models.TextField("开发任务开始通用提示词", blank=True, default="")
    test_task_prompt = models.TextField("测试任务开始通用提示词", blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_work_groups",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "工作群"
        verbose_name_plural = "工作群"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.project.name} - {self.name}"


class WorkGroupMember(models.Model):
    """工作群成员。"""

    group = models.ForeignKey(WorkGroup, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="work_group_memberships"
    )
    joined_at = models.DateTimeField("加入时间", auto_now_add=True)

    class Meta:
        verbose_name = "工作群成员"
        verbose_name_plural = "工作群成员"
        unique_together = ("group", "user")

    def __str__(self):
        return f"{self.group.name}-{self.user.username}"


class WorkGroupMessage(models.Model):
    """工作群消息。"""

    group = models.ForeignKey(WorkGroup, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="work_group_messages"
    )
    content = models.TextField("消息内容")
    created_at = models.DateTimeField("发送时间", auto_now_add=True)

    class Meta:
        verbose_name = "工作群消息"
        verbose_name_plural = "工作群消息"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.group.name}-{self.sender.username}-{self.created_at:%m-%d %H:%M}"
