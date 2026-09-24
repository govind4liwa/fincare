"""Tax API routes (mounted under /api/v1/)."""

from rest_framework.routers import DefaultRouter

from apps.tax.views import CorporateTaxReturnViewSet, TaxCodeRateHistoryViewSet, TaxReturnViewSet

router = DefaultRouter()
router.register("tax-rate-history", TaxCodeRateHistoryViewSet, basename="tax-rate-history")
router.register("vat-returns", TaxReturnViewSet, basename="vat-return")
router.register("corporate-tax-returns", CorporateTaxReturnViewSet, basename="corporate-tax-return")

urlpatterns = router.urls
