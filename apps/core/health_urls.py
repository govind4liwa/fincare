"""Health endpoints mounted at /health/ (no API prefix, no auth).

Used by the Docker HEALTHCHECK and external load-balancer probes.
"""
from django.urls import path

from . import views

urlpatterns = [
    path("", views.liveness, name="health"),
    path("ready/", views.readiness, name="readiness"),
]
