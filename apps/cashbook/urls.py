"""Cashbook API routes (mounted under /api/v1/)."""

from rest_framework.routers import DefaultRouter

from apps.cashbook.views import (
    CashAccountViewSet,
    CashCountViewSet,
    PettyCashFloatViewSet,
    ReplenishmentViewSet,
)

router = DefaultRouter()
router.register("cash-accounts", CashAccountViewSet, basename="cash-account")
router.register("petty-cash-floats", PettyCashFloatViewSet, basename="petty-cash-float")
router.register("replenishments", ReplenishmentViewSet, basename="replenishment")
router.register("cash-counts", CashCountViewSet, basename="cash-count")

urlpatterns = router.urls
