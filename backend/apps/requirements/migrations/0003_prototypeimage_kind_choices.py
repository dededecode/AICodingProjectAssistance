from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("requirements", "0002_prototypeimage"),
    ]

    operations = [
        migrations.AlterField(
            model_name="prototypeimage",
            name="kind",
            field=models.CharField(
                choices=[
                    ("prototype", "原型图"),
                    ("ui", "UI图"),
                    ("flow", "业务流程图"),
                    ("other", "其它"),
                ],
                default="prototype",
                max_length=20,
                verbose_name="类型",
            ),
        ),
    ]
