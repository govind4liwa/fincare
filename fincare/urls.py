"""FinCare — root URL configuration."""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenVerifyView

api_v1_patterns = [
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("core/", include("apps.core.urls")),
    path("tenants/", include("apps.tenants.urls")),  # /api/v1/tenants/{entities,branches}/
    path("", include("apps.accounts.urls")),  # /api/v1/{accounts,account-groups,tax-codes}/
    path("", include("apps.ar.urls")),  # /api/v1/customers/
    path("", include("apps.ap.urls")),  # /api/v1/suppliers/
    path("", include("apps.ledger.urls")),  # /api/v1/periods/
    path("", include("apps.fleet.urls")),  # /api/v1/vehicles/
    path("", include("apps.drivers.urls")),  # /api/v1/drivers/
    path("", include("apps.vouchers.urls")),  # /api/v1/vouchers/
    path("reports/", include("apps.reports.urls")),  # /api/v1/reports/<code>/
    # Future:
    # path("users/", include("apps.users.urls")),
    # path("accounts/", include("apps.accounts.urls")),
    # path("ledger/", include("apps.ledger.urls")),
    # ...
]

urlpatterns = [
    path("admin/", admin.site.urls),
    # System endpoints (no API version prefix)
    path("health/", include("apps.core.health_urls")),
    # API
    path("api/v1/", include((api_v1_patterns, "v1"), namespace="v1")),
    # OpenAPI
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/schema/swagger/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger"),
    path("api/schema/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns += [
        path("__debug__/", include(debug_toolbar.urls)),
        path("silk/", include("silk.urls", namespace="silk")),
    ]
