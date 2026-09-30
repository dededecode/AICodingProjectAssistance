from django.conf import settings
from django.db import models


def normalize_doc_type(value):
    """把任意类型值/历史旧值归一为 4 类交付文档类型之一，无法识别归入「其它」。"""
    v = (value or "").strip()
    if not v:
        return "other"
    low = v.lower()
    if low in ("architecture", "testing", "deployment", "other"):
        return low
    if any(k in v for k in ("架构", "设计", "architect", "design")):
        return "architecture"
    if any(k in v for k in ("测试", "报告", "test")):
        return "testing"
    if any(k in v for k in ("部署", "运维", "deploy", "install")):
        return "deployment"
    return "other"


class DeliveryDoc(models.Model):
    """交付文档（架构设计/测试/部署/其它，4 类固定类型）。"""

    SOURCE_CHOICES = [("agent", "Agent 回传"), ("manual", "手动上传")]

    DOC_TYPE_CHOICES = [
        ("architecture", "架构设计文档"),
        ("testing", "测试文档"),
        ("deployment", "部署文档"),
        ("other", "其它"),
    ]

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="delivery_docs"
    )
    title = models.CharField("文档标题", max_length=300)
    doc_type = models.CharField("文档类型", max_length=30, choices=DOC_TYPE_CHOICES, default="other")
    content = models.TextField("文档内容(markdown)", blank=True, default="")
    file = models.FileField("附件", upload_to="delivery/", null=True, blank=True)
    source = models.CharField("来源", max_length=20, choices=SOURCE_CHOICES, default="manual")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "交付文档"
        verbose_name_plural = "交付文档"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
