"""Drivers API routes (mounted under /api/v1/)."""

from rest_framework.routers import DefaultRouter

from apps.drivers.views import AdvanceViewSet, DriverViewSet, SettlementViewSet

router = DefaultRouter()
router.register("drivers", DriverViewSet, basename="driver")
router.register("driver-advances", AdvanceViewSet, basename="driver-advance")
router.register("driver-settlements", SettlementViewSet, basename="driver-settlement")

urlpatterns = router.urls
