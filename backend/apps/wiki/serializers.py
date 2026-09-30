from rest_framework import serializers

from .models import WikiPage


class WikiPageSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    page_type_display = serializers.CharField(source="get_page_type_display", read_only=True)
    source_type_display = serializers.CharField(source="get_source_type_display", read_only=True)

    class Meta:
        model = WikiPage
        fields = "__all__"
