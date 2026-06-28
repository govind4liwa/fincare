"""Core app — system endpoints."""

from __future__ import annotations

import django
from django.conf import settings
from django.db import connection

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from drf_spectacular.utils import OpenApiResponse, extend_schema


@extend_schema(
    tags=["core"],
    summary="Liveness probe",
    description="Returns 200 if the Django process is alive. Does not check dependencies.",
    responses={200: OpenApiResponse(description="Service is alive")},
)
@api_view(["GET"])
@permission_classes([AllowAny])
def liveness(request: Request) -> Response:
    return Response(
        {
            "status": "ok",
            "service": "fincare",
            "version": "0.1.0",
            "django": django.get_version(),
        }
    )


@extend_schema(
    tags=["core"],
    summary="Readiness probe",
    description=(
        "Returns 200 only if the service and all critical dependencies (DB, cache) "
        "are reachable. Returns 503 otherwise."
    ),
    responses={
        200: OpenApiResponse(description="Service and dependencies are healthy"),
        503: OpenApiResponse(description="One or more dependencies unreachable"),
    },
)
@api_view(["GET"])
@permission_classes([AllowAny])
def readiness(request: Request) -> Response:
    checks: dict[str, str] = {}
    overall_ok = True

    # --- Database ---
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        checks["database"] = "ok"
    except Exception as exc:
        overall_ok = False
        checks["database"] = f"error: {exc.__class__.__name__}"

    # --- Cache ---
    try:
        from django.core.cache import cache

        cache.set("__healthcheck__", "1", timeout=5)
        if cache.get("__healthcheck__") == "1":
            checks["cache"] = "ok"
        else:
            overall_ok = False
            checks["cache"] = "error: roundtrip mismatch"
    except Exception as exc:
        overall_ok = False
        checks["cache"] = f"error: {exc.__class__.__name__}"

    payload = {
        "status": "ok" if overall_ok else "degraded",
        "service": "fincare",
        "version": "0.1.0",
        "checks": checks,
        "environment": (
            settings.SETTINGS_MODULE if hasattr(settings, "SETTINGS_MODULE") else "unknown"
        ),
    }
    http_status = status.HTTP_200_OK if overall_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    return Response(payload, status=http_status)
