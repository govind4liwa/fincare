"""Settings API routes (mounted under /api/v1/)."""

from rest_framework.routers import DefaultRouter

from apps.settings.views import DriverAccountingConfigViewSet

router = DefaultRouter()
router.register(
    "driver-accounting-config",
    DriverAccountingConfigViewSet,
    basename="driver-accounting-config",
)

urlpatterns = router.urls
