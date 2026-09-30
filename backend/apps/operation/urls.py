from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import OperationItemViewSet, OperationMetricViewSet

router = DefaultRouter()
router.register("operation-items", OperationItemViewSet, basename="operationitem")
router.register("operation-metrics", OperationMetricViewSet, basename="operationmetric")

urlpatterns = [
    path("", include(router.urls)),
]
