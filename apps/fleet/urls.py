"""Fleet API routes (mounted under /api/v1/)."""

from rest_framework.routers import DefaultRouter

from apps.fleet.views import (
    LoanInstallmentViewSet,
    LoanScheduleViewSet,
    VehicleLoanViewSet,
    VehicleViewSet,
)

router = DefaultRouter()
router.register("vehicles", VehicleViewSet, basename="vehicle")
router.register("vehicle-loans", VehicleLoanViewSet, basename="vehicle-loan")
router.register("loan-schedules", LoanScheduleViewSet, basename="loan-schedule")
router.register("loan-installments", LoanInstallmentViewSet, basename="loan-installment")

urlpatterns = router.urls
