# 把存量交付文档的 doc_type 归一为 4 类固定类型（架构设计/测试/部署/其它）。
from django.db import migrations, models

from apps.delivery.models import normalize_doc_type


def normalize_existing(apps, schema_editor):
    DeliveryDoc = apps.get_model("delivery", "DeliveryDoc")
    for doc in DeliveryDoc.objects.all():
        key = normalize_doc_type(doc.doc_type)
        if key != doc.doc_type:
            doc.doc_type = key
            doc.save(update_fields=["doc_type"])


class Migration(migrations.Migration):

    dependencies = [
        ("delivery", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(normalize_existing, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="deliverydoc",
            name="doc_type",
            field=models.CharField(
                choices=[
                    ("architecture", "架构设计文档"),
                    ("testing", "测试文档"),
                    ("deployment", "部署文档"),
                    ("other", "其它"),
                ],
                default="other",
                max_length=30,
                verbose_name="文档类型",
            ),
        ),
    ]
