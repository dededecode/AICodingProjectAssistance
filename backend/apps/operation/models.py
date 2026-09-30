from django.conf import settings
from django.db import models


class OperationItem(models.Model):
    """运营记录：迭代需求 / 优化需求 / 业务变更 / 用户反馈。"""

    CATEGORY_CHOICES = [
        ("iteration", "迭代需求"),
        ("optimization", "优化需求"),
        ("change", "业务变更"),
        ("feedback", "用户反馈"),
    ]
    PRIORITY_CHOICES = [("low", "低"), ("medium", "中"), ("high", "高")]
    STATUS_CHOICES = [
        ("evaluating", "待评估"),
        ("accepted", "已接受"),
        ("scheduled", "已安排"),
        ("online", "已上线"),
        ("closed", "已关闭"),
    ]

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="operation_items"
    )
    category = models.CharField("类型", max_length=20, choices=CATEGORY_CHOICES, default="iteration")
    title = models.CharField("标题", max_length=200)
    content = models.TextField("内容/描述", blank=True, default="")
    priority = models.CharField("优先级", max_length=20, choices=PRIORITY_CHOICES, default="medium")
    status = models.CharField("状态", max_length=20, choices=STATUS_CHOICES, default="evaluating")
    requestor = models.CharField("提出人", max_length=50, blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "运营记录"
        verbose_name_plural = "运营记录"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class OperationMetric(models.Model):
    """运营指标（按月）：续期/续费、满意度、活跃用户等。"""

    INDICATOR_CHOICES = [
        ("renewal", "续期/续费"),
        ("satisfaction", "满意度"),
        ("active_users", "活跃用户"),
        ("custom", "自定义"),
    ]

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="operation_metrics"
    )
    month = models.CharField("月份", max_length=7, help_text="YYYY-MM")
    indicator = models.CharField("指标", max_length=20, choices=INDICATOR_CHOICES, default="custom")
    value = models.FloatField("数值", default=0)
    note = models.CharField("说明", max_length=200, blank=True, default="")
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "运营指标"
        verbose_name_plural = "运营指标"
        ordering = ["-month", "id"]
        unique_together = ["project", "month", "indicator"]

    def __str__(self):
        return f"{self.month} {self.get_indicator_display()}: {self.value}"
