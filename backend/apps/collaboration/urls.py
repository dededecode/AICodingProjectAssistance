from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import WeeklySummaryViewSet, WorkGroupViewSet, WorkLogViewSet

router = DefaultRouter()
router.register("work-logs", WorkLogViewSet, basename="worklog")
router.register("weekly-summaries", WeeklySummaryViewSet, basename="weeklysummary")
router.register("work-groups", WorkGroupViewSet, basename="workgroup")

urlpatterns = [
    path("", include(router.urls)),
]
