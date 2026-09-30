from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("project_planning", "0004_plantask"),
    ]

    operations = [
        migrations.AddField(
            model_name="plantask",
            name="ui_images",
            field=models.JSONField(blank=True, default=list, verbose_name="关联原型图/UI图名称列表"),
        ),
    ]
