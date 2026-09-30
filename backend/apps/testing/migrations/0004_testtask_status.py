# 测试任务状态新增「待复测(retest)」「已关闭(closed)」

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("testing", "0003_bug_module_bugimage"),
    ]

    operations = [
        migrations.AlterField(
            model_name="testtask",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "待执行"),
                    ("executing", "执行中"),
                    ("passed", "通过"),
                    ("failed", "失败"),
                    ("blocked", "阻塞"),
                    ("retest", "待复测"),
                    ("closed", "已关闭"),
                ],
                default="pending",
                max_length=20,
                verbose_name="状态",
            ),
        ),
    ]
