"""Integrations API routes (mounted under /api/v1/)."""

from rest_framework.routers import DefaultRouter

from apps.integrations.views import ImportBatchViewSet, ImportProfileViewSet

router = DefaultRouter()
router.register("import-profiles", ImportProfileViewSet, basename="import-profile")
router.register("import-batches", ImportBatchViewSet, basename="import-batch")

urlpatterns = router.urls
