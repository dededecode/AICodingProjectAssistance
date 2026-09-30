from django.conf import settings
from django.db import models


class WikiPage(models.Model):
    """LLM Wiki 知识页：由 LLM 从项目源文档编译生成（覆盖式重建），与知识库向量物理隔离。"""

    PAGE_TYPE_CHOICES = [
        ("overview", "总览"),
        ("module", "业务模块"),
        ("entity", "实体/概念"),
        ("table", "数据表"),
        ("api", "接口"),
        ("timeline", "时间线"),
        ("synthesis", "综合分析"),
    ]
    SOURCE_TYPE_CHOICES = [
        ("requirement", "需求文档"),
        ("architecture", "架构设计"),
        ("plan", "项目计划"),
        ("delivery", "交付文档"),
    ]

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="wiki_pages"
    )
    source_type = models.CharField("来源类型", max_length=20, choices=SOURCE_TYPE_CHOICES)
    source_id = models.IntegerField("来源 id")
    source_title = models.CharField("来源标题", max_length=300, blank=True, default="")
    source_updated_at = models.DateTimeField("编译时来源时间快照", null=True, blank=True)
    page_type = models.CharField("页面类型", max_length=20, choices=PAGE_TYPE_CHOICES, default="synthesis")
    title = models.CharField("页面标题", max_length=300)
    content = models.TextField("页面内容(markdown)")
    links = models.JSONField("关联页面标题", default=list, blank=True)
    sources = models.JSONField("来源引用", default=list, blank=True)
    compiled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="wiki_pages_compiled",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "Wiki 页面"
        verbose_name_plural = "Wiki 页面"
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title


class WikiCompileLog(models.Model):
    """Wiki 编译日志：记录每次编译的来源、结果、耗时与操作者。"""

    STATUS_CHOICES = [("success", "成功"), ("failed", "失败")]

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="wiki_compile_logs"
    )
    source_type = models.CharField("来源类型", max_length=20, choices=WikiPage.SOURCE_TYPE_CHOICES)
    source_id = models.IntegerField("来源 id")
    source_title = models.CharField("来源标题", max_length=300, blank=True, default="")
    status = models.CharField("状态", max_length=10, choices=STATUS_CHOICES, default="success")
    page_count = models.IntegerField("生成页面数", default=0)
    error = models.TextField("失败原因", blank=True, default="")
    duration_ms = models.IntegerField("耗时(毫秒)", default=0)
    meta = models.JSONField("附加信息", default=dict, blank=True)
    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "Wiki 编译日志"
        verbose_name_plural = "Wiki 编译日志"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_source_type_display()}#{self.source_id} {self.status}"
