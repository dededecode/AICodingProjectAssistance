from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import PrototypeImageViewSet, RequirementViewSet

router = DefaultRouter()
router.register("requirements", RequirementViewSet, basename="requirement")
router.register("prototype-images", PrototypeImageViewSet, basename="prototype-image")

urlpatterns = [
    path("", include(router.urls)),
]
