from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("wiki", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="wikicompilelog",
            name="meta",
            field=models.JSONField(blank=True, default=dict, verbose_name="附加信息"),
        ),
    ]
