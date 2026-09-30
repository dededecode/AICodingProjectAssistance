from rest_framework import serializers

from .models import BASE_FRAMEWORK_CHOICES, DB_TYPE_CHOICES, ArchitectureDesign


class ArchitectureDesignSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    creator = serializers.CharField(source="created_by.username", read_only=True, default="")
    base_framework_display = serializers.CharField(source="get_base_framework_display", read_only=True)
    db_type_display = serializers.CharField(source="get_db_type_display", read_only=True)

    class Meta:
        model = ArchitectureDesign
        fields = [
            "id",
            "project",
            "project_name",
            "frontend_stack",
            "backend_stack",
            "base_framework",
            "base_framework_display",
            "db_type",
            "db_type_display",
            "design_doc",
            "db_sql",
            "creator",
            "created_at",
        ]
        read_only_fields = ["project_name", "creator", "base_framework_display", "db_type_display", "created_at"]


class ArchitectureGenerateSerializer(serializers.Serializer):
    project_id = serializers.IntegerField()
    frontend_stack = serializers.CharField(max_length=200)
    backend_stack = serializers.CharField(max_length=200)
    base_framework = serializers.ChoiceField(choices=[c[0] for c in BASE_FRAMEWORK_CHOICES], required=False, allow_blank=True, default="")
    db_type = serializers.ChoiceField(choices=[c[0] for c in DB_TYPE_CHOICES], default="mysql")
    # 用户补充的约束/规则、其它信息，随提示词一起发给 AI
    constraints = serializers.CharField(required=False, allow_blank=True, default="")
    extra = serializers.CharField(required=False, allow_blank=True, default="")
