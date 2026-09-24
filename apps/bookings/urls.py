"""Bookings API routes (mounted under /api/v1/)."""

from rest_framework.routers import DefaultRouter

from apps.bookings.views import ContractViewSet, TripViewSet

router = DefaultRouter()
router.register("trips", TripViewSet, basename="trip")
router.register("contracts", ContractViewSet, basename="contract")

urlpatterns = router.urls
