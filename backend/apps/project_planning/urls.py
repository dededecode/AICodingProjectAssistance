from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import PlanTaskViewSet, ProjectPlanViewSet

router = DefaultRouter()
router.register("project-plans", ProjectPlanViewSet, basename="projectplan")
router.register("plan-tasks", PlanTaskViewSet, basename="plantask")

urlpatterns = [
    path("", include(router.urls)),
]
