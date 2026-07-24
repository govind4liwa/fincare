"""Core app URLs mounted under /api/v1/core/."""

from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("liveness/", views.liveness, name="liveness"),
    path("readiness/", views.readiness, name="readiness"),
]
