from django.conf import settings
from django.db import models


class Requirement(models.Model):
    """项目需求文档及其分析结果。"""

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="requirements"
    )
    title = models.CharField("文档标题", max_length=300)
    original_file = models.FileField("原始文件", upload_to="requirements/", null=True, blank=True)
    file_path = models.CharField("文件绝对路径", max_length=1000, blank=True, default="")
    parsed_text = models.TextField("解析后的文本", blank=True, default="")
    analysis_result = models.JSONField("AI 完整度分析结果", null=True, blank=True)
    is_confirmed = models.BooleanField("是否确认入库", default=False)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "需求文档"
        verbose_name_plural = "需求文档"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class PrototypeImage(models.Model):
    """原型图 / UI 图（客户上传，按项目管理）。"""

    KIND_CHOICES = [
        ("prototype", "原型图"),
        ("ui", "UI图"),
        ("flow", "业务流程图"),
        ("other", "其它"),
    ]

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="prototype_images"
    )
    name = models.CharField("图名称", max_length=100, help_text="建议按格式取名：端-模块-功能，如 Web-登录-验证码")
    kind = models.CharField("类型", max_length=20, choices=KIND_CHOICES, default="prototype")
    image = models.FileField("图片", upload_to="prototypes/")
    uploader = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "原型/UI图"
        verbose_name_plural = "原型/UI图"
        ordering = ["-created_at"]
        unique_together = ("project", "name")

    def __str__(self):
        return self.name
