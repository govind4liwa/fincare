"""Admin for the Payroll module."""

from django.contrib import admin

from apps.payroll.models import (
    Advance,
    Employee,
    EmployeeSalary,
    Gratuity,
    Leave,
    Payslip,
    PayslipLine,
    Run,
    SalaryComponent,
    WpsBatch,
    WpsRecord,
)


class EmployeeSalaryInline(admin.TabularInline):
    model = EmployeeSalary
    extra = 0


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "designation", "pay_method", "entity", "status")
    list_filter = ("status", "pay_method", "entity")
    search_fields = ("code", "name", "emirates_id", "mol_personal_no")
    inlines = [EmployeeSalaryInline]


@admin.register(SalaryComponent)
class SalaryComponentAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "component_type", "is_gratuity_base", "is_wps_fixed", "entity")
    list_filter = ("component_type", "is_gratuity_base", "is_wps_fixed")
    search_fields = ("code", "name")


class PayslipLineInline(admin.TabularInline):
    model = PayslipLine
    extra = 0


class PayslipInline(admin.TabularInline):
    model = Payslip
    extra = 0
    readonly_fields = ("gross_earnings", "total_deductions", "advance_recovery", "net_pay")


@admin.register(Run)
class RunAdmin(admin.ModelAdmin):
    list_display = ("salary_month", "run_date", "gross_total", "net_total", "status", "entity")
    list_filter = ("status", "entity")
    date_hierarchy = "run_date"
    inlines = [PayslipInline]
    readonly_fields = (
        "gross_total",
        "deduction_total",
        "net_total",
        "journal_entry",
        "payment_entry",
    )


@admin.register(Payslip)
class PayslipAdmin(admin.ModelAdmin):
    list_display = ("run", "employee", "gross_earnings", "total_deductions", "net_pay", "status")
    list_filter = ("status",)
    inlines = [PayslipLineInline]


class WpsRecordInline(admin.TabularInline):
    model = WpsRecord
    extra = 0
    readonly_fields = ("fixed_amount", "variable_amount")


@admin.register(WpsBatch)
class WpsBatchAdmin(admin.ModelAdmin):
    inlines = [WpsRecordInline]
    list_display = (
        "salary_month",
        "employer_eid",
        "total_records",
        "fixed_total",
        "variable_total",
        "total_salary",
        "status",
    )
    list_filter = ("status",)


@admin.register(Gratuity)
class GratuityAdmin(admin.ModelAdmin):
    list_display = ("employee", "as_of_date", "type", "service_years", "amount", "status")
    list_filter = ("type", "status", "entity")
    date_hierarchy = "as_of_date"


@admin.register(Leave)
class LeaveAdmin(admin.ModelAdmin):
    list_display = ("employee", "leave_type", "balance_days", "accrued_amount", "as_of_date")
    list_filter = ("leave_type", "entity")


@admin.register(Advance)
class AdvanceAdmin(admin.ModelAdmin):
    list_display = ("employee", "advance_date", "amount", "recovered_amount", "balance", "status")
    list_filter = ("status", "entity")
    date_hierarchy = "advance_date"
    search_fields = ("employee__code", "employee__name")
