"""AR API routes (mounted under /api/v1/)."""

from rest_framework.routers import DefaultRouter

from apps.ar.views import CustomerViewSet, SalesInvoiceViewSet

router = DefaultRouter()
router.register("customers", CustomerViewSet, basename="customer")
router.register("invoices", SalesInvoiceViewSet, basename="invoice")

urlpatterns = router.urls
