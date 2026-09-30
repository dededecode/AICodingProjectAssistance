from django.conf import settings
from django.db import models


class UserAiConfig(models.Model):
    """每个用户各自的大模型（LLM）与多模态（Vision）配置。
    请求模型时优先用当前登录用户的配置，未配置则回退环境变量。"""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ai_config"
    )
    llm_base_url = models.CharField("LLM Base URL", max_length=500, blank=True, default="")
    llm_api_key = models.CharField("LLM API Key", max_length=500, blank=True, default="")
    llm_model = models.CharField("LLM 模型", max_length=200, blank=True, default="")

    vision_base_url = models.CharField("多模态 Base URL", max_length=500, blank=True, default="")
    vision_api_key = models.CharField("多模态 API Key", max_length=500, blank=True, default="")
    vision_model = models.CharField("多模态模型", max_length=200, blank=True, default="")

    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "用户模型配置"
        verbose_name_plural = "用户模型配置"

    def __str__(self):
        return f"{self.user.username} 模型配置"


class AiConfig(models.Model):
    """全局共享配置（当前仅 Embedding）：本地/远程嵌入模型对全体用户一致，
    避免不同用户用不同嵌入模型导致向量库混乱。"""

    EMBEDDING_MODE_CHOICES = [("local", "本地(local)"), ("remote", "远程(remote)")]

    # LLM
    llm_base_url = models.CharField("LLM Base URL", max_length=500, blank=True, default="")
    llm_api_key = models.CharField("LLM API Key", max_length=500, blank=True, default="")
    llm_model = models.CharField("LLM 模型", max_length=200, blank=True, default="")

    # 多模态 LLM（vision）
    vision_base_url = models.CharField("多模态 Base URL", max_length=500, blank=True, default="")
    vision_api_key = models.CharField("多模态 API Key", max_length=500, blank=True, default="")
    vision_model = models.CharField("多模态模型", max_length=200, blank=True, default="")

    # Embedding
    embedding_mode = models.CharField(
        "Embedding 模式", max_length=20, choices=EMBEDDING_MODE_CHOICES, blank=True, default=""
    )
    embedding_model = models.CharField("本地 Embedding 模型", max_length=300, blank=True, default="")
    llm_embedding_base_url = models.CharField("远程 Embedding Base URL", max_length=500, blank=True, default="")
    llm_embedding_model = models.CharField("远程 Embedding 模型", max_length=200, blank=True, default="")

    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "模型配置"
        verbose_name_plural = "模型配置"

    @classmethod
    def load(cls):
        """返回单行配置，不存在时创建默认空配置。"""
        obj, _ = cls.objects.get_or_create(id=1)
        return obj

    def save(self, *args, **kwargs):
        # 强制单行
        self.id = 1
        super().save(*args, **kwargs)


class EmbeddingCallLog(models.Model):
    """嵌入模型远程调用日志：记录调用时间与调用账号（便于审计 key 使用方）。"""

    username = models.CharField("调用账号", max_length=150, blank=True, default="", help_text="实际使用的 API Key 归属账号；未匹配用户时为 env")
    called_at = models.DateTimeField("调用时间", auto_now_add=True)

    class Meta:
        verbose_name = "嵌入模型调用日志"
        verbose_name_plural = "嵌入模型调用日志"
        ordering = ["-called_at"]

    def __str__(self):
        return f"{self.username} @ {self.called_at}"
