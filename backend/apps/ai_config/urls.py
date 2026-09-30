from django.urls import path

from .views import AiConfigView, AiTestView, EmbeddingLogView

urlpatterns = [
    path("ai-config/", AiConfigView.as_view(), name="ai-config"),
    path("ai-config/test/", AiTestView.as_view(), name="ai-config-test"),
    path("ai-config/embedding-logs/", EmbeddingLogView.as_view(), name="ai-config-embedding-logs"),
]
