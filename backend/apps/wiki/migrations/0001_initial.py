import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("projects", "0002_alter_project_status"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="WikiPage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "source_type",
                    models.CharField(
                        choices=[
                            ("requirement", "需求文档"),
                            ("architecture", "架构设计"),
                            ("plan", "项目计划"),
                            ("delivery", "交付文档"),
                        ],
                        max_length=20,
                        verbose_name="来源类型",
                    ),
                ),
                ("source_id", models.IntegerField(verbose_name="来源 id")),
                ("source_title", models.CharField(blank=True, default="", max_length=300, verbose_name="来源标题")),
                ("source_updated_at", models.DateTimeField(blank=True, null=True, verbose_name="编译时来源时间快照")),
                (
                    "page_type",
                    models.CharField(
                        choices=[
                            ("overview", "总览"),
                            ("module", "业务模块"),
                            ("entity", "实体/概念"),
                            ("table", "数据表"),
                            ("api", "接口"),
                            ("timeline", "时间线"),
                            ("synthesis", "综合分析"),
                        ],
                        default="synthesis",
                        max_length=20,
                        verbose_name="页面类型",
                    ),
                ),
                ("title", models.CharField(max_length=300, verbose_name="页面标题")),
                ("content", models.TextField(verbose_name="页面内容(markdown)")),
                ("links", models.JSONField(blank=True, default=list, verbose_name="关联页面标题")),
                ("sources", models.JSONField(blank=True, default=list, verbose_name="来源引用")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
                (
                    "compiled_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="wiki_pages_compiled",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="wiki_pages",
                        to="projects.project",
                    ),
                ),
            ],
            options={
                "verbose_name": "Wiki 页面",
                "verbose_name_plural": "Wiki 页面",
                "ordering": ["-updated_at"],
            },
        ),
        migrations.CreateModel(
            name="WikiCompileLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "source_type",
                    models.CharField(
                        choices=[
                            ("requirement", "需求文档"),
                            ("architecture", "架构设计"),
                            ("plan", "项目计划"),
                            ("delivery", "交付文档"),
                        ],
                        max_length=20,
                        verbose_name="来源类型",
                    ),
                ),
                ("source_id", models.IntegerField(verbose_name="来源 id")),
                ("source_title", models.CharField(blank=True, default="", max_length=300, verbose_name="来源标题")),
                (
                    "status",
                    models.CharField(
                        choices=[("success", "成功"), ("failed", "失败")], default="success", max_length=10, verbose_name="状态"
                    ),
                ),
                ("page_count", models.IntegerField(default=0, verbose_name="生成页面数")),
                ("error", models.TextField(blank=True, default="", verbose_name="失败原因")),
                ("duration_ms", models.IntegerField(default=0, verbose_name="耗时(毫秒)")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                (
                    "operator",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="wiki_compile_logs",
                        to="projects.project",
                    ),
                ),
            ],
            options={
                "verbose_name": "Wiki 编译日志",
                "verbose_name_plural": "Wiki 编译日志",
                "ordering": ["-created_at"],
            },
        ),
    ]
