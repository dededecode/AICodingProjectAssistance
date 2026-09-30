from rest_framework import serializers

from .models import Bug, BugImage, TestCase, TestTask


class BugSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    severity_display = serializers.CharField(source="get_severity_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    assignee_name = serializers.CharField(source="assignee.username", read_only=True, default="")
    reporter_name = serializers.CharField(source="reporter.username", read_only=True, default="")
    related_test_task_name = serializers.CharField(source="related_test_task.test_case.name", read_only=True, default="")
    related_task_title = serializers.CharField(source="related_task.title", read_only=True, default="")
    related_task_module = serializers.CharField(source="related_task.module", read_only=True, default="")
    images = serializers.SerializerMethodField()

    class Meta:
        model = Bug
        fields = [
            "id", "project", "project_name", "title", "description", "module",
            "severity", "severity_display", "status", "status_display",
            "assignee", "assignee_name", "related_test_task", "related_test_task_name",
            "related_task", "related_task_title", "related_task_module",
            "reporter", "reporter_name", "images", "created_at", "updated_at",
        ]
        read_only_fields = ["project_name", "severity_display", "status_display", "assignee_name", "reporter_name", "related_test_task_name", "related_task_title", "related_task_module", "reporter", "images", "created_at", "updated_at"]

    def get_images(self, obj):
        return [{"id": im.id, "url": im.image.url} for im in obj.images.all()]


class BugFromTestSerializer(serializers.Serializer):
    """从失败/阻塞的测试任务一键转缺陷。"""
    test_task_id = serializers.IntegerField()
    title = serializers.CharField(required=False, allow_blank=True)
    module = serializers.CharField(required=False, allow_blank=True)
    severity = serializers.ChoiceField(choices=Bug.SEVERITY_CHOICES, default="medium")
    assignee_id = serializers.IntegerField(required=False)


class TestCaseSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)

    class Meta:
        model = TestCase
        fields = ["id", "project", "project_name", "module", "name", "description", "priority", "expected_result", "created_at"]
        read_only_fields = ["project_name", "created_at"]


class TestTaskSerializer(serializers.ModelSerializer):
    test_case_name = serializers.CharField(source="test_case.name", read_only=True)
    test_case_module = serializers.CharField(source="test_case.module", read_only=True, default="")
    assignee_name = serializers.CharField(source="assignee.username", read_only=True)

    class Meta:
        model = TestTask
        fields = ["id", "test_case", "test_case_name", "test_case_module", "assignee", "assignee_name", "status", "result", "created_at", "updated_at"]
        read_only_fields = ["test_case_name", "test_case_module", "assignee_name", "created_at", "updated_at"]


class TestTaskCreateSerializer(serializers.Serializer):
    test_case_id = serializers.IntegerField()
    assignee_id = serializers.IntegerField()


class TestTaskBatchDispatchSerializer(serializers.Serializer):
    """批量派单：多个用例一次性指派给同一执行人。"""
    test_case_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)
    assignee_id = serializers.IntegerField()
