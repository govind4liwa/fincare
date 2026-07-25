"""Banking API routes (mounted under /api/v1/)."""

from rest_framework.routers import DefaultRouter

from apps.banking.views import BankAccountViewSet, BankStatementViewSet, ReconciliationViewSet

router = DefaultRouter()
router.register("bank-accounts", BankAccountViewSet, basename="bank-account")
router.register("bank-statements", BankStatementViewSet, basename="bank-statement")
router.register("reconciliations", ReconciliationViewSet, basename="reconciliation")

urlpatterns = router.urls
