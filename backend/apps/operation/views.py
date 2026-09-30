from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import OperationItem, OperationMetric
from .serializers import OperationItemSerializer, OperationMetricSerializer


class OperationItemViewSet(viewsets.ModelViewSet):
    queryset = OperationItem.objects.select_related("project").all()
    serializer_class = OperationItemSerializer

    def get_queryset(self):
        qs = self.queryset
        project_id = self.request.query_params.get("project_id")
        category = self.request.query_params.get("category")
        status = self.request.query_params.get("status")
        if project_id:
            qs = qs.filter(project_id=project_id)
        if category:
            qs = qs.filter(category=category)
        if status:
            qs = qs.filter(status=status)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user if self.request.user.is_authenticated else None)

    @action(detail=False, methods=["get"], url_path="statistics")
    def statistics(self, request):
        """运营记录统计：按类型与状态分布。"""
        project_id = request.query_params.get("project_id")
        qs = OperationItem.objects.all()
        if project_id:
            qs = qs.filter(project_id=project_id)
        by_category = {k: qs.filter(category=k).count() for k, _ in OperationItem.CATEGORY_CHOICES}
        by_status = {k: qs.filter(status=k).count() for k, _ in OperationItem.STATUS_CHOICES}
        total = qs.count()
        open_count = total - by_status.get("closed", 0)
        return Response({"total": total, "open": open_count, "by_category": by_category, "by_status": by_status})


class OperationMetricViewSet(viewsets.ModelViewSet):
    queryset = OperationMetric.objects.select_related("project").all()
    serializer_class = OperationMetricSerializer

    def get_queryset(self):
        qs = self.queryset
        project_id = self.request.query_params.get("project_id")
        month = self.request.query_params.get("month")
        if project_id:
            qs = qs.filter(project_id=project_id)
        if month:
            qs = qs.filter(month=month)
        return qs
