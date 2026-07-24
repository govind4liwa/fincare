"""Fleet API routes (mounted under /api/v1/)."""

from rest_framework.routers import DefaultRouter

from apps.fleet.views import VehicleViewSet

router = DefaultRouter()
router.register("vehicles", VehicleViewSet, basename="vehicle")

urlpatterns = router.urls
