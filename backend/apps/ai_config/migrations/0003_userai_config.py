# 新增 UserAiConfig（每个用户各自 LLM/Vision 配置）
# 并把旧的全局 AiConfig(id=1) 中 LLM/Vision 回填到管理员，保证现状不丢

import django.conf
import django.db.models.deletion
from django.db import migrations, models


def backfill_admin(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    AiConfig = apps.get_model("ai_config", "AiConfig")
    UserAiConfig = apps.get_model("ai_config", "UserAiConfig")
    admin = User.objects.filter(username="admin").first() or User.objects.filter(role="admin").first()
    if not admin:
        return
    g = AiConfig.objects.filter(id=1).first()
    if not g:
        return
    UserAiConfig.objects.update_or_create(
        user=admin,
        defaults={
            "llm_base_url": g.llm_base_url or "",
            "llm_api_key": g.llm_api_key or "",
            "llm_model": g.llm_model or "",
            "vision_base_url": g.vision_base_url or "",
            "vision_api_key": g.vision_api_key or "",
            "vision_model": g.vision_model or "",
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("ai_config", "0002_aiconfig_vision_api_key_aiconfig_vision_base_url_and_more"),
        ("accounts", "0004_user_mcp_token"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserAiConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("llm_base_url", models.CharField(blank=True, default="", max_length=500, verbose_name="LLM Base URL")),
                ("llm_api_key", models.CharField(blank=True, default="", max_length=500, verbose_name="LLM API Key")),
                ("llm_model", models.CharField(blank=True, default="", max_length=200, verbose_name="LLM 模型")),
                ("vision_base_url", models.CharField(blank=True, default="", max_length=500, verbose_name="多模态 Base URL")),
                ("vision_api_key", models.CharField(blank=True, default="", max_length=500, verbose_name="多模态 API Key")),
                ("vision_model", models.CharField(blank=True, default="", max_length=200, verbose_name="多模态模型")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ai_config",
                        to=django.conf.settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"verbose_name": "用户模型配置", "verbose_name_plural": "用户模型配置"},
        ),
        migrations.RunPython(backfill_admin, migrations.RunPython.noop),
    ]
