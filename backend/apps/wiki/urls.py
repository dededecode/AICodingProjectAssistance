from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import WikiPageViewSet

router = DefaultRouter()
router.register("wiki", WikiPageViewSet, basename="wiki")

urlpatterns = [
    path("", include(router.urls)),
]
