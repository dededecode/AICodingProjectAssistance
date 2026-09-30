from rest_framework import serializers

from .models import OperationItem, OperationMetric


class OperationItemSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    category_display = serializers.CharField(source="get_category_display", read_only=True)
    priority_display = serializers.CharField(source="get_priority_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = OperationItem
        fields = [
            "id", "project", "project_name", "category", "category_display",
            "title", "content", "priority", "priority_display", "status", "status_display",
            "requestor", "created_by", "created_at", "updated_at",
        ]
        read_only_fields = ["project_name", "category_display", "priority_display", "status_display", "created_by", "created_at", "updated_at"]


class OperationMetricSerializer(serializers.ModelSerializer):
    indicator_display = serializers.CharField(source="get_indicator_display", read_only=True)

    class Meta:
        model = OperationMetric
        fields = ["id", "project", "month", "indicator", "indicator_display", "value", "note", "created_at"]
        read_only_fields = ["indicator_display", "created_at"]
