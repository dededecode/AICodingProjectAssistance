# 新增 User.mcp_token：先加非唯一字段，回填随机令牌后再加唯一约束（避免 SQLite 多行空串冲突）

import secrets

from django.db import migrations, models


def _gen():
    return "mcp-" + secrets.token_urlsafe(24)


def backfill(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    for user in User.objects.filter(mcp_token="").iterator():
        user.mcp_token = _gen()
        user.save(update_fields=["mcp_token"])


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_user_capability"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="mcp_token",
            field=models.CharField(
                blank=True,
                default="",
                max_length=64,
                verbose_name="MCP Token",
            ),
        ),
        migrations.RunPython(backfill, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="user",
            name="mcp_token",
            field=models.CharField(
                blank=True,
                default="",
                help_text="MCP 与平台接口通信的令牌，标识该用户身份",
                max_length=64,
                unique=True,
                verbose_name="MCP Token",
            ),
        ),
    ]
