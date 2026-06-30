"""Voucher API routes (mounted under /api/v1/)."""

from rest_framework.routers import DefaultRouter

from apps.vouchers.views import VoucherViewSet

router = DefaultRouter()
router.register("vouchers", VoucherViewSet, basename="voucher")

urlpatterns = router.urls
