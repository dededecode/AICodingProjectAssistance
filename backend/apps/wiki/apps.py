from django.apps import AppConfig


class WikiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.wiki"
    verbose_name = "LLM Wiki 知识库"
