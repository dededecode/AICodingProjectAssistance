from rest_framework import serializers

from services.db_crypto import dec, enc

from .models import AiConfig, UserAiConfig

_KEY_FIELDS = ("llm_api_key", "vision_api_key")


def mask_key(value: str) -> str:
    """掩码 API Key（明文）：保留前 3 后 4 位，中间用 **** 代替；空值原样返回。"""
    value = dec(value or "")
    if len(value) <= 8:
        return "****" if value else ""
    return f"{value[:3]}****{value[-4:]}"


class UserAiConfigSerializer(serializers.ModelSerializer):
    """当前用户自己的 LLM/Vision 配置。
    Key 存库加密（enc:v1: 前缀）；读取时解密后掩码返回；写入时掩码占位则保留原值。"""

    class Meta:
        model = UserAiConfig
        fields = [
            "id",
            "llm_base_url",
            "llm_api_key",
            "llm_model",
            "vision_base_url",
            "vision_api_key",
            "vision_model",
            "updated_at",
        ]
        read_only_fields = ["id", "updated_at"]

    def to_representation(self, obj):
        data = super().to_representation(obj)
        for f in _KEY_FIELDS:
            data[f] = mask_key(data.get(f))
        return data

    def _encrypt_keys(self, validated_data, instance=None):
        """Key 加密入库；提交的是掩码占位 → 未改动，保留原值。"""
        for f in _KEY_FIELDS:
            v = validated_data.get(f)
            if v is None:
                continue
            if instance is not None and v == mask_key(getattr(instance, f, "")):
                validated_data.pop(f)
            elif v:
                validated_data[f] = enc(v)
        return validated_data

    def create(self, validated_data):
        return super().create(self._encrypt_keys(validated_data))

    def update(self, instance, validated_data):
        return super().update(instance, self._encrypt_keys(validated_data, instance))


class EmbeddingConfigSerializer(serializers.ModelSerializer):
    """全局共享的 Embedding 配置（仅管理员可改）。"""

    class Meta:
        model = AiConfig
        fields = [
            "embedding_mode",
            "embedding_model",
            "llm_embedding_base_url",
            "llm_embedding_model",
            "updated_at",
        ]
        read_only_fields = ["updated_at"]


class AiTestSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=["llm", "embedding", "vision"])
