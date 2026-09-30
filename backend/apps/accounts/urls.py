from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import AdminUserViewSet, CaptchaView, ChangePasswordView, LoginView, MeView, RsaPublicKeyView, UserListView

router = DefaultRouter()
router.register("admin-users", AdminUserViewSet, basename="adminuser")

urlpatterns = [
    path("captcha/", CaptchaView.as_view(), name="auth-captcha"),
    path("rsa-public-key/", RsaPublicKeyView.as_view(), name="auth-rsa-public-key"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    path("me/", MeView.as_view(), name="auth-me"),
    path("users/", UserListView.as_view(), name="auth-users"),
    path("change-password/", ChangePasswordView.as_view(), name="auth-change-password"),
    path("", include(router.urls)),
]
