from django.urls import path

from .views import MyResourcesView, RoleCreateView, RoleDeleteView, RoleListView, RoleResourceSaveView

urlpatterns = [
    path("rbac/roles/", RoleListView.as_view(), name="rbac-roles"),
    path("rbac/roles/create/", RoleCreateView.as_view(), name="rbac-roles-create"),
    path("rbac/roles/<int:pk>/resources/", RoleResourceSaveView.as_view(), name="rbac-roles-resources"),
    path("rbac/roles/<int:pk>/delete/", RoleDeleteView.as_view(), name="rbac-roles-delete"),
    path("rbac/my-resources/", MyResourcesView.as_view(), name="rbac-my-resources"),
]
