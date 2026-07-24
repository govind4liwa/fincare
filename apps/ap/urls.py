"""AP API routes (mounted under /api/v1/)."""

from rest_framework.routers import DefaultRouter

from apps.ap.views import SupplierViewSet

router = DefaultRouter()
router.register("suppliers", SupplierViewSet, basename="supplier")

urlpatterns = router.urls
