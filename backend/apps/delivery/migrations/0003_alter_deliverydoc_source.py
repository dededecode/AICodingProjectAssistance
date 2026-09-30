# 将来源标识归一为通用名 agent：把历史遗留的非 manual 来源值统一改写
from django.db import migrations, models


def to_agent(apps, schema_editor):
    """把历史遗留的非 manual 来源值统一归一为 agent。"""
    DeliveryDoc = apps.get_model("delivery", "DeliveryDoc")
    DeliveryDoc.objects.exclude(source="manual").update(source="agent")


class Migration(migrations.Migration):

    dependencies = [
        ("delivery", "0002_deliverydoc_doc_type_normalize"),
    ]

    operations = [
        # 反向为 noop：0001 已声明 agent，回滚后取值与 choices 保持一致
        migrations.RunPython(to_agent, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="deliverydoc",
            name="source",
            field=models.CharField(
                choices=[("agent", "Agent 回传"), ("manual", "手动上传")],
                default="manual",
                max_length=20,
                verbose_name="来源",
            ),
        ),
    ]
