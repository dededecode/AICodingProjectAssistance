# 新增 EmbeddingCallLog（嵌入模型远程调用日志：调用时间 + 调用账号）

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ai_config", "0003_userai_config"),
    ]

    operations = [
        migrations.CreateModel(
            name="EmbeddingCallLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "username",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="实际使用的 API Key 归属账号；未匹配用户时为 env",
                        max_length=150,
                        verbose_name="调用账号",
                    ),
                ),
                ("called_at", models.DateTimeField(auto_now_add=True, verbose_name="调用时间")),
            ],
            options={
                "verbose_name": "嵌入模型调用日志",
                "verbose_name_plural": "嵌入模型调用日志",
                "ordering": ["-called_at"],
            },
        ),
    ]
