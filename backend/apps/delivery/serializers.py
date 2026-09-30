from rest_framework import serializers

from .models import DeliveryDoc


class DeliveryDocSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    creator = serializers.CharField(source="created_by.username", read_only=True, default="")
    doc_type_display = serializers.CharField(source="get_doc_type_display", read_only=True)

    class Meta:
        model = DeliveryDoc
        fields = ["id", "project", "project_name", "title", "doc_type", "doc_type_display", "content", "file", "source", "creator", "created_at"]
        read_only_fields = ["project_name", "creator", "created_at"]


class DeliveryDocContentUploadSerializer(serializers.Serializer):
    """Agent 内容回传（doc_type 由视图归一为 4 类固定类型）。"""
    project_id = serializers.IntegerField()
    title = serializers.CharField()
    type = serializers.CharField(required=False, allow_blank=True)
    content = serializers.CharField()
