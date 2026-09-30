from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Project, ProjectMember

User = get_user_model()


class ProjectSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source="owner.username", read_only=True)
    status_display = serializers.SerializerMethodField()
    members = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            "id",
            "name",
            "description",
            "owner",
            "owner_name",
            "status",
            "status_display",
            "members",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["owner", "created_at", "updated_at"]

    def get_status_display(self, obj):
        return obj.get_status_display()

    def get_members(self, obj):
        links = obj.member_links.select_related("user").all()
        return [
            {
                "id": link.user.id,
                "username": link.user.username,
                "role": link.role,
                "role_display": link.get_role_display(),
            }
            for link in links
        ]

    def create(self, validated_data):
        request = self.context.get("request")
        project = Project.objects.create(**validated_data, owner=request.user)
        ProjectMember.objects.create(project=project, user=request.user, role="manager")
        return project


class MemberInviteSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    role = serializers.ChoiceField(choices=ProjectMember.ROLE_CHOICES, default="developer")
