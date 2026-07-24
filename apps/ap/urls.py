"""AP API routes (mounted under /api/v1/)."""

from rest_framework.routers import DefaultRouter

from apps.ap.views import DebitNoteViewSet, PurchaseBillViewSet, SupplierViewSet

router = DefaultRouter()
router.register("suppliers", SupplierViewSet, basename="supplier")
router.register("bills", PurchaseBillViewSet, basename="bill")
router.register("debit-notes", DebitNoteViewSet, basename="debit-note")

urlpatterns = router.urls
