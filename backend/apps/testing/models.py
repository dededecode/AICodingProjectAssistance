from django.conf import settings
from django.db import models


class Bug(models.Model):
    """缺陷单。"""

    SEVERITY_CHOICES = [("low", "低"), ("medium", "中"), ("high", "高"), ("critical", "严重")]
    STATUS_CHOICES = [("new", "待处理"), ("processing", "处理中"), ("fixed", "已修复"), ("retest", "待复测"), ("closed", "已关闭")]

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="bugs"
    )
    title = models.CharField("缺陷标题", max_length=200)
    description = models.TextField("缺陷描述", blank=True, default="")
    module = models.CharField("业务模块", max_length=100, blank=True, default="")
    severity = models.CharField("严重程度", max_length=20, choices=SEVERITY_CHOICES, default="medium")
    status = models.CharField("状态", max_length=20, choices=STATUS_CHOICES, default="new")
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="bugs_assigned"
    )
    related_test_task = models.ForeignKey(
        "TestTask", on_delete=models.SET_NULL, null=True, blank=True, related_name="bugs"
    )
    related_task = models.ForeignKey(
        "project_planning.PlanTask", on_delete=models.SET_NULL, null=True, blank=True, related_name="bugs"
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="bugs_reported"
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "缺陷"
        verbose_name_plural = "缺陷"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class BugImage(models.Model):
    """缺陷附件图片（截图/证据）。"""

    bug = models.ForeignKey(Bug, on_delete=models.CASCADE, related_name="images")
    image = models.FileField("图片", upload_to="bugs/")
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "缺陷图片"
        verbose_name_plural = "缺陷图片"
        ordering = ["-created_at"]

    def __str__(self):
        return f"bug-{self.bug_id}-image"


class TestCase(models.Model):
    """测试用例。"""

    PRIORITY_CHOICES = [("low", "低"), ("medium", "中"), ("high", "高")]

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="test_cases"
    )
    module = models.CharField("所属模块", max_length=100, blank=True, default="")
    name = models.CharField("用例名称", max_length=200)
    description = models.TextField("用例描述", blank=True, default="")
    priority = models.CharField("优先级", max_length=20, choices=PRIORITY_CHOICES, default="medium")
    expected_result = models.TextField("预期结果", blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "测试用例"
        verbose_name_plural = "测试用例"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class TestTask(models.Model):
    """测试派单。"""

    STATUS_CHOICES = [
        ("pending", "待执行"),
        ("executing", "执行中"),
        ("passed", "通过"),
        ("failed", "失败"),
        ("blocked", "阻塞"),
        ("retest", "待复测"),
        ("closed", "已关闭"),
    ]

    test_case = models.ForeignKey(
        TestCase, on_delete=models.CASCADE, related_name="tasks"
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="test_tasks"
    )
    status = models.CharField("状态", max_length=20, choices=STATUS_CHOICES, default="pending")
    result = models.TextField("测试结果/说明", blank=True, default="")
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "测试任务"
        verbose_name_plural = "测试任务"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.test_case.name} - {self.assignee.username}"
