"""Platforms API routes (mounted under /api/v1/)."""

from rest_framework.routers import DefaultRouter

from apps.platforms.views import EarningImportViewSet, PlatformSettlementViewSet, PlatformViewSet

router = DefaultRouter()
router.register("platforms", PlatformViewSet, basename="platform")
router.register("earning-imports", EarningImportViewSet, basename="earning-import")
router.register("platform-settlements", PlatformSettlementViewSet, basename="platform-settlement")

urlpatterns = router.urls
