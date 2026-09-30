from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("collaboration", "0003_workgroup"),
    ]

    operations = [
        migrations.AddField(
            model_name="workgroup",
            name="status",
            field=models.CharField(choices=[("active", "活跃"), ("dismissed", "已解散")], default="active", max_length=20, verbose_name="群状态"),
        ),
    ]
