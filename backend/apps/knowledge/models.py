from django.conf import settings
from django.db import models


class KnowledgeItem(models.Model):
    """项目知识条目（新增记录，便于列表展示；向量内容存于 Chroma）。"""

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="knowledge_items"
    )
    content = models.TextField("知识内容")
    source = models.CharField("来源标记", max_length=50, blank=True, default="manual")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "项目知识"
        verbose_name_plural = "项目知识"
        ordering = ["-created_at"]

    def __str__(self):
        return self.content[:50]
