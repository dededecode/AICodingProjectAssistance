from rest_framework import serializers

from .models import PlanTask, ProjectPlan, ProjectPlanMember


class PlanTaskSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    plan_name = serializers.CharField(source="plan.name", read_only=True, default="")
    assignee_name = serializers.CharField(source="assignee.username", read_only=True, default="")
    difficulty_display = serializers.CharField(source="get_difficulty_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = PlanTask
        fields = [
            "id",
            "plan",
            "plan_name",
            "project",
            "project_name",
            "title",
            "description",
            "module",
            "difficulty",
            "difficulty_display",
            "estimated_days",
            "assignee",
            "assignee_name",
            "status",
            "status_display",
            "start_date",
            "end_date",
            "depends",
            "ui_images",
            "sort_order",
            "created_at",
        ]
        read_only_fields = ["project_name", "plan_name", "assignee_name", "difficulty_display", "status_display", "created_at"]


class ProjectPlanSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    requirement_title = serializers.CharField(source="requirement.title", read_only=True, default="")
    creator = serializers.CharField(source="created_by.username", read_only=True, default="")
    members = serializers.SerializerMethodField()
    task_count = serializers.SerializerMethodField()

    class Meta:
        model = ProjectPlan
        fields = [
            "id",
            "project",
            "project_name",
            "name",
            "requirement",
            "requirement_title",
            "planned_members",
            "start_date",
            "launch_date",
            "plan_content",
            "members",
            "task_count",
            "creator",
            "created_at",
        ]
        read_only_fields = ["project_name", "requirement_title", "creator", "created_at"]

    def get_members(self, obj):
        return [
            {
                "user_id": m.user_id,
                "username": m.user.username,
                "weight": m.weight,
            }
            for m in obj.members.select_related("user").all()
        ]

    def get_task_count(self, obj):
        return obj.tasks.count()


class PlanMemberSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    weight = serializers.FloatField(min_value=0.0, max_value=1.0)


class ProjectPlanGenerateSerializer(serializers.Serializer):
    project_id = serializers.IntegerField()
    requirement_id = serializers.IntegerField()
    name = serializers.CharField(max_length=200)
    start_date = serializers.DateField()
    launch_date = serializers.DateField()
    members = PlanMemberSerializer(many=True, allow_empty=False)
