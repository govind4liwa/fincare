"""Fleet API routes (mounted under /api/v1/)."""

from rest_framework.routers import DefaultRouter

from apps.fleet.views import (
    DepreciationRunViewSet,
    LoanInstallmentViewSet,
    LoanScheduleViewSet,
    VehicleDocumentViewSet,
    VehicleLoanViewSet,
    VehicleViewSet,
)

router = DefaultRouter()
router.register("vehicles", VehicleViewSet, basename="vehicle")
router.register("vehicle-documents", VehicleDocumentViewSet, basename="vehicle-document")
router.register("vehicle-loans", VehicleLoanViewSet, basename="vehicle-loan")
router.register("loan-schedules", LoanScheduleViewSet, basename="loan-schedule")
router.register("loan-installments", LoanInstallmentViewSet, basename="loan-installment")
router.register("depreciation-runs", DepreciationRunViewSet, basename="depreciation-run")

urlpatterns = router.urls
