from rest_framework import serializers

from .models import KnowledgeItem


class KnowledgeItemSerializer(serializers.ModelSerializer):
    creator = serializers.CharField(source="created_by.username", read_only=True, default="")

    class Meta:
        model = KnowledgeItem
        fields = ["id", "project", "content", "creator", "created_at"]
        read_only_fields = ["creator", "created_at"]


class KnowledgeAddSerializer(serializers.Serializer):
    project_id = serializers.IntegerField()
    text = serializers.CharField()


class KnowledgeSearchSerializer(serializers.Serializer):
    project_id = serializers.IntegerField()
    query = serializers.CharField()
    top_k = serializers.IntegerField(default=5, min_value=1, max_value=20)
