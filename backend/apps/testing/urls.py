from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import BugViewSet, TestCaseViewSet, TestTaskViewSet

router = DefaultRouter()
router.register("test-cases", TestCaseViewSet, basename="testcase")
router.register("test-tasks", TestTaskViewSet, basename="testtask")
router.register("bugs", BugViewSet, basename="bug")

urlpatterns = [
    path("", include(router.urls)),
]
