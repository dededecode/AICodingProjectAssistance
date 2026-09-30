from rest_framework import serializers

from .models import PrototypeImage, Requirement


class RequirementSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)

    class Meta:
        model = Requirement
        fields = [
            "id",
            "project",
            "project_name",
            "title",
            "original_file",
            "parsed_text",
            "analysis_result",
            "is_confirmed",
            "created_at",
        ]
        read_only_fields = ["parsed_text", "analysis_result", "is_confirmed", "created_at"]


class PrototypeImageSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    uploader_name = serializers.CharField(source="uploader.username", read_only=True, default="")
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)

    class Meta:
        model = PrototypeImage
        fields = [
            "id",
            "project",
            "project_name",
            "name",
            "kind",
            "kind_display",
            "image",
            "uploader_name",
            "created_at",
        ]
        read_only_fields = ["project_name", "uploader_name", "kind_display", "created_at"]
