# 建表 + 初始化内置 5 个角色 Group（与 accounts.User.role 对应）。
from django.contrib.auth.models import Group
from django.db import migrations, models


def create_builtin_groups(apps, schema_editor):
    for name in ["admin", "manager", "developer", "tester", "guest"]:
        Group.objects.get_or_create(name=name)


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.CreateModel(
            name="RoleResource",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("code", models.CharField(max_length=100, verbose_name="资源码")),
                (
                    "resource_type",
                    models.CharField(
                        choices=[
                            ("menu", "菜单"),
                            ("btn", "按钮"),
                            ("api", "接口"),
                        ],
                        max_length=20,
                        verbose_name="资源类型",
                    ),
                ),
                (
                    "group",
                    models.ForeignKey(
                        on_delete=models.CASCADE,
                        related_name="rbac_resources",
                        to="auth.group",
                    ),
                ),
            ],
            options={
                "verbose_name": "角色资源",
                "verbose_name_plural": "角色资源",
                "unique_together": {("group", "code")},
            },
        ),
        migrations.RunPython(create_builtin_groups, migrations.RunPython.noop),
    ]
