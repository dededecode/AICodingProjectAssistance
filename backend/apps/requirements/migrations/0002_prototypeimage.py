# 原型图/UI图管理：新增 PrototypeImage 模型

import django.conf
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("requirements", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PrototypeImage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(help_text="建议按格式取名：端-模块-功能，如 Web-登录-验证码", max_length=100, verbose_name="图名称")),
                ("kind", models.CharField(choices=[("prototype", "原型图"), ("ui", "UI图")], default="prototype", max_length=20, verbose_name="类型")),
                ("image", models.FileField(upload_to="prototypes/", verbose_name="图片")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                (
                    "uploader",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=django.conf.settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="prototype_images",
                        to="projects.project",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "verbose_name": "原型/UI图",
                "verbose_name_plural": "原型/UI图",
                "unique_together": {("project", "name")},
            },
        ),
    ]
