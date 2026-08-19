"""Payroll API routes (mounted under /api/v1/)."""

from rest_framework.routers import DefaultRouter

from apps.payroll.views import (
    AdvanceViewSet,
    EmployeeSalaryViewSet,
    EmployeeViewSet,
    PayslipViewSet,
    RunViewSet,
    SalaryComponentViewSet,
)

router = DefaultRouter()
router.register("salary-components", SalaryComponentViewSet, basename="salary-component")
router.register("employees", EmployeeViewSet, basename="employee")
router.register("employee-salaries", EmployeeSalaryViewSet, basename="employee-salary")
router.register("payroll-runs", RunViewSet, basename="payroll-run")
router.register("payslips", PayslipViewSet, basename="payslip")
router.register("payroll-advances", AdvanceViewSet, basename="payroll-advance")

urlpatterns = router.urls
