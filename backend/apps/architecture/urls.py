from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ArchitectureViewSet

router = DefaultRouter()
router.register("architecture", ArchitectureViewSet, basename="architecture")

urlpatterns = [
    path("", include(router.urls)),
]
