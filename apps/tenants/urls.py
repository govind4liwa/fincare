"""Tenancy API routes (mounted under /api/v1/tenants/)."""

from rest_framework.routers import DefaultRouter

from apps.tenants.views import BranchViewSet, EntityViewSet

router = DefaultRouter()
router.register("entities", EntityViewSet, basename="entity")
router.register("branches", BranchViewSet, basename="branch")

urlpatterns = router.urls
