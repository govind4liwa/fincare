"""Chart of Accounts API routes (mounted under /api/v1/)."""

from rest_framework.routers import DefaultRouter

from apps.accounts.views import AccountGroupViewSet, AccountViewSet, TaxCodeViewSet

router = DefaultRouter()
router.register("accounts", AccountViewSet, basename="account")
router.register("account-groups", AccountGroupViewSet, basename="account-group")
router.register("tax-codes", TaxCodeViewSet, basename="tax-code")

urlpatterns = router.urls
