from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("collaboration", "0002_worklog_tasks"),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkGroup",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200, verbose_name="群名称")),
                ("workflow_desc", models.TextField(blank=True, default="", verbose_name="工作流程定义")),
                ("dev_task_prompt", models.TextField(blank=True, default="", verbose_name="开发任务开始通用提示词")),
                ("test_task_prompt", models.TextField(blank=True, default="", verbose_name="测试任务开始通用提示词")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        blank=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_work_groups",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="work_groups",
                        to="projects.project",
                    ),
                ),
            ],
            options={
                "verbose_name": "工作群",
                "verbose_name_plural": "工作群",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="WorkGroupMember",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("joined_at", models.DateTimeField(auto_now_add=True, verbose_name="加入时间")),
                (
                    "group",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="members", to="collaboration.workgroup"),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="work_group_memberships",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "工作群成员",
                "verbose_name_plural": "工作群成员",
                "unique_together": {("group", "user")},
            },
        ),
        migrations.CreateModel(
            name="WorkGroupMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("content", models.TextField(verbose_name="消息内容")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="发送时间")),
                (
                    "group",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="messages", to="collaboration.workgroup"),
                ),
                (
                    "sender",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="work_group_messages",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "工作群消息",
                "verbose_name_plural": "工作群消息",
                "ordering": ["created_at"],
            },
        ),
    ]
