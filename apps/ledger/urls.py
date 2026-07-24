"""Ledger API routes (mounted under /api/v1/)."""

from rest_framework.routers import DefaultRouter

from apps.ledger.views import AccountingPeriodViewSet

router = DefaultRouter()
router.register("periods", AccountingPeriodViewSet, basename="period")

urlpatterns = router.urls
