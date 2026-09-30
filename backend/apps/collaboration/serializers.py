from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.project_planning.models import PlanTask
from .models import WeeklySummary, WorkGroup, WorkGroupMember, WorkGroupMessage, WorkLog

User = get_user_model()


class WorkLogSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)
    # user 非必填：未传或非特权用户传 user_id 时，默认登记到当前用户（见 create）
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False, allow_null=True)
    tasks = serializers.PrimaryKeyRelatedField(many=True, required=False, queryset=PlanTask.objects.all())
    tasks_display = serializers.SerializerMethodField()

    class Meta:
        model = WorkLog
        fields = ["id", "project", "project_name", "user", "username", "date", "hours", "description", "tasks", "tasks_display", "created_at"]
        read_only_fields = ["username", "project_name", "created_at"]

    def get_tasks_display(self, obj):
        return [t.title for t in obj.tasks.all()]

    def create(self, validated_data):
        tasks = validated_data.pop("tasks", [])
        requester = self.context["request"].user
        user = validated_data.get("user")
        # 非特权用户只能登记到自己名下
        if not user or not (requester.is_superuser or requester.role in ("admin", "manager")):
            user = requester
        validated_data["user"] = user
        log = super().create(validated_data)
        log.tasks.set(tasks)
        return log

    def update(self, instance, validated_data):
        tasks = validated_data.pop("tasks", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if tasks is not None:
            instance.tasks.set(tasks)
        return instance


class WorkLogStatSerializer(serializers.Serializer):
    """工时统计：按项目/成员汇总。"""
    project_id = serializers.IntegerField(required=False)
    user_id = serializers.IntegerField(required=False)
    start = serializers.DateField(required=False)
    end = serializers.DateField(required=False)


class WeeklySummarySerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)

    class Meta:
        model = WeeklySummary
        fields = ["id", "project", "project_name", "user", "username", "week_start", "content", "created_at", "updated_at"]
        read_only_fields = ["user", "username", "project_name", "created_at", "updated_at"]

    def create(self, validated_data):
        user = self.context["request"].user
        # 同一成员/项目/周只保留一条，重复提交则更新
        obj, _ = WeeklySummary.objects.update_or_create(
            project=validated_data["project"],
            user=user,
            week_start=validated_data["week_start"],
            defaults={"content": validated_data.get("content", "")},
        )
        return obj


class WorkGroupMemberSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = WorkGroupMember
        fields = ["id", "user", "username", "joined_at"]


class WorkGroupSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    creator = serializers.CharField(source="created_by.username", read_only=True, default="")
    members = serializers.SerializerMethodField()

    class Meta:
        model = WorkGroup
        fields = [
            "id",
            "project",
            "project_name",
            "name",
            "status",
            "workflow_desc",
            "dev_task_prompt",
            "test_task_prompt",
            "creator",
            "members",
            "created_at",
        ]
        read_only_fields = ["project_name", "creator", "members", "created_at"]

    def get_members(self, obj):
        return WorkGroupMemberSerializer(obj.members.select_related("user").all(), many=True).data

    def create(self, validated_data):
        request = self.context["request"]
        group = WorkGroup.objects.create(created_by=request.user if request.user.is_authenticated else None, **validated_data)
        # 创建者自动入群
        if request.user.is_authenticated:
            WorkGroupMember.objects.get_or_create(group=group, user=request.user)
        return group


class WorkGroupMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source="sender.username", read_only=True)

    class Meta:
        model = WorkGroupMessage
        fields = ["id", "group", "sender", "sender_name", "content", "created_at"]
        read_only_fields = ["sender", "sender_name", "created_at"]
