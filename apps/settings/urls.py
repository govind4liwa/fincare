"""Settings API routes (mounted under /api/v1/)."""

from rest_framework.routers import DefaultRouter

from apps.settings.views import DriverAccountingConfigViewSet, EntitySettingViewSet

router = DefaultRouter()
router.register(
    "driver-accounting-config",
    DriverAccountingConfigViewSet,
    basename="driver-accounting-config",
)
router.register("entity-settings", EntitySettingViewSet, basename="entity-settings")

urlpatterns = router.urls
