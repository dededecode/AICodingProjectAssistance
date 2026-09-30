"""把数据库中已存的明文 API Key 加密入库（幂等，可重复执行）。

用法：python manage.py encrypt_api_keys
部署切换加密存储后执行一次；已带 enc:v1: 前缀的字段自动跳过。
主密钥：环境变量 PLATFORM_DB_SECRET（缺省从 DJANGO_SECRET_KEY 派生），
执行时与后续运行时必须一致，否则解不开。
"""
from django.core.management.base import BaseCommand

from apps.ai_config.models import AiConfig, UserAiConfig
from services.db_crypto import enc, is_encrypted

_FIELDS = ("llm_api_key", "vision_api_key")


class Command(BaseCommand):
    help = "把 AiConfig / UserAiConfig 中已存的明文 API Key 加密（幂等）"

    def handle(self, *args, **options):
        total = 0
        for model in (AiConfig, UserAiConfig):
            name = model.__name__
            for obj in model.objects.all().iterator():
                changed = []
                for f in _FIELDS:
                    v = (getattr(obj, f) or "").strip()
                    if v and not is_encrypted(v):
                        setattr(obj, f, enc(v))
                        changed.append(f)
                if changed:
                    obj.save(update_fields=changed)
                    total += len(changed)
                    self.stdout.write(f"{name}#{obj.id}: 已加密 {', '.join(changed)}")
        self.stdout.write(self.style.SUCCESS(f"完成：共加密 {total} 个字段"))
