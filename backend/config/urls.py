"""URL configuration for the platform backend."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/", include("apps.projects.urls")),
    path("api/", include("apps.requirements.urls")),
    path("api/", include("apps.knowledge.urls")),
    path("api/", include("apps.collaboration.urls")),
    path("api/", include("apps.testing.urls")),
    path("api/", include("apps.delivery.urls")),
    path("api/", include("apps.ai_config.urls")),
    path("api/", include("apps.project_planning.urls")),
    path("api/", include("apps.architecture.urls")),
    path("api/", include("apps.operation.urls")),
    path("api/", include("apps.wiki.urls")),
    path("api/", include("apps.rbac.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
