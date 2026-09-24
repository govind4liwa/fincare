"""Users API routes (mounted under /api/v1/)."""

from django.urls import path

from apps.users.views import MeView

urlpatterns = [
    path("users/me/", MeView.as_view(), name="me"),
]
