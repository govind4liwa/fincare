"""DRF serializers for payroll: salary components, employees, salary structure,
the run -> payslip lifecycle, salary advances, WPS/SIF batches, and gratuity/leave
accrual."""

import logging

from rest_framework import serializers

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
from apps.payroll.services.engine import PayrollError
from apps.payroll.services.gratuity import accrue_gratuity
from apps.payroll.services.leave import accrue_leave
from apps.payroll.services.wps import generate_wps

logger = logging.getLogger(__name__)


class SalaryComponentSerializer(serializers.ModelSerializer):
    account_code = serializers.CharField(source="account.code", read_only=True)

    class Meta:
        model = SalaryComponent
        fields = [
            "id",
            "entity",
            "code",
            "name",
            "component_type",
            "is_gratuity_base",
            "is_wps_fixed",
            "account",
            "account_code",
            "is_active",
        ]


class EmployeeSalarySerializer(serializers.ModelSerializer):
    component_code = serializers.CharField(source="component.code", read_only=True)
    component_name = serializers.CharField(source="component.name", read_only=True)
    component_type = serializers.CharField(source="component.component_type", read_only=True)

    class Meta:
        model = EmployeeSalary
        fields = [
            "id",
            "employee",
            "component",
            "component_code",
            "component_name",
            "component_type",
            "amount",
            "effective_from",
            "effective_to",
        ]


class EmployeeSerializer(serializers.ModelSerializer):
    driver_code = serializers.CharField(source="driver.code", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    payable_account_code = serializers.CharField(source="payable_account.code", read_only=True)
    salary = EmployeeSalarySerializer(many=True, read_only=True)

    class Meta:
        model = Employee
        fields = [
            "id",
            "entity",
            "code",
            "name",
            "driver",
            "driver_code",
            "emirates_id",
            "passport_no",
            "nationality",
            "join_date",
            "designation",
            "department",
            "department_name",
            "branch",
            "mol_personal_no",
            "work_permit_no",
            "pay_method",
            "bank_routing_code",
            "iban",
            "payable_account",
            "payable_account_code",
            "status",
            "left_date",
            "salary",
        ]


class PayslipLineSerializer(serializers.ModelSerializer):
    component_code = serializers.CharField(source="component.code", read_only=True)

    class Meta:
        model = PayslipLine
        fields = ["id", "component", "component_code", "component_type", "amount"]


class PayslipSerializer(serializers.ModelSerializer):
    """Payslips are a byproduct of `RunViewSet.build` — never created directly."""

    employee_code = serializers.CharField(source="employee.code", read_only=True)
    employee_name = serializers.CharField(source="employee.name", read_only=True)
    lines = PayslipLineSerializer(many=True, read_only=True)

    class Meta:
        model = Payslip
        fields = [
            "id",
            "run",
            "employee",
            "employee_code",
            "employee_name",
            "working_days",
            "lop_days",
            "gross_earnings",
            "total_deductions",
            "advance_recovery",
            "net_pay",
            "status",
            "lines",
        ]


class RunSerializer(serializers.ModelSerializer):
    """A draft names entity/salary_month/run_date; `build` derives payslips from
    the current salary structure, `post` books the accrual, `pay` books the
    payment. Totals and postings are all server-derived."""

    payslips = PayslipSerializer(many=True, read_only=True)

    class Meta:
        model = Run
        fields = [
            "id",
            "entity",
            "period",
            "salary_month",
            "run_date",
            "gross_total",
            "deduction_total",
            "net_total",
            "status",
            "journal_entry",
            "payment_entry",
            "approved_by",
            "payslips",
        ]
        read_only_fields = [
            "gross_total",
            "deduction_total",
            "net_total",
            "status",
            "journal_entry",
            "payment_entry",
            "approved_by",
            "payslips",
        ]


class AdvanceSerializer(serializers.ModelSerializer):
    """A draft names employee/amount/installments (+ optional installment_amount
    for an uneven split — left blank/zero, `pay` computes an even split);
    `pay` books DR Staff Advances / CR Bank and sets recovered_amount/balance.
    Recovery afterwards happens automatically inside a payroll run's `build`."""

    employee_code = serializers.CharField(source="employee.code", read_only=True)
    employee_name = serializers.CharField(source="employee.name", read_only=True)

    class Meta:
        model = Advance
        fields = [
            "id",
            "entity",
            "employee",
            "employee_code",
            "employee_name",
            "advance_date",
            "amount",
            "installments",
            "installment_amount",
            "recovered_amount",
            "balance",
            "advance_account",
            "bank_account",
            "journal_entry",
            "status",
        ]
        read_only_fields = ["recovered_amount", "balance", "journal_entry", "status"]


class WpsRecordSerializer(serializers.ModelSerializer):
    employee_code = serializers.CharField(source="employee.code", read_only=True)
    employee_name = serializers.CharField(source="employee.name", read_only=True)

    class Meta:
        model = WpsRecord
        fields = [
            "id",
            "employee",
            "employee_code",
            "employee_name",
            "mol_personal_no",
            "bank_routing_code",
            "iban",
            "pay_start_date",
            "pay_end_date",
            "working_days",
            "fixed_amount",
            "variable_amount",
            "leave_days",
            "notes",
        ]


class WpsBatchSerializer(serializers.ModelSerializer):
    """Create names run/employer_eid/employer_bank_routing; `generate_wps`
    builds one record per WPS-paid employee on that run's payslips and the
    batch totals — every other field here is that derived output."""

    records = WpsRecordSerializer(many=True, read_only=True)

    class Meta:
        model = WpsBatch
        fields = [
            "id",
            "run",
            "employer_eid",
            "employer_bank_routing",
            "salary_month",
            "total_records",
            "total_salary",
            "fixed_total",
            "variable_total",
            "sif_file_ref",
            "status",
            "generated_at",
            "records",
        ]
        read_only_fields = [
            "salary_month",
            "total_records",
            "total_salary",
            "fixed_total",
            "variable_total",
            "sif_file_ref",
            "status",
            "generated_at",
            "records",
        ]

    def create(self, validated_data):
        try:
            return generate_wps(
                validated_data["run"],
                employer_eid=validated_data["employer_eid"],
                employer_bank_routing=validated_data["employer_bank_routing"],
                user=self.context["request"].user,
            )
        except PayrollError as exc:
            logger.warning("WPS batch generation rejected: %s", exc)
            raise serializers.ValidationError(
                {"non_field_errors": ["Could not generate the WPS batch for this run."]}
            ) from exc


class GratuitySerializer(serializers.ModelSerializer):
    """Create names employee/as_of_date/provision_account/expense_account (+
    optional basis_salary override); `accrue_gratuity` computes service years,
    eligible days, and the amount, then books DR Expense / CR Provision.
    Settlement is a separate action — see `GratuityViewSet.settle`."""

    employee_code = serializers.CharField(source="employee.code", read_only=True)
    employee_name = serializers.CharField(source="employee.name", read_only=True)
    basis_salary = serializers.DecimalField(
        max_digits=18, decimal_places=2, required=False, allow_null=True
    )

    class Meta:
        model = Gratuity
        fields = [
            "id",
            "entity",
            "employee",
            "employee_code",
            "employee_name",
            "as_of_date",
            "service_years",
            "basis_salary",
            "eligible_days",
            "amount",
            "type",
            "provision_account",
            "expense_account",
            "bank_account",
            "journal_entry",
            "status",
        ]
        read_only_fields = [
            "entity",
            "service_years",
            "eligible_days",
            "amount",
            "type",
            "bank_account",
            "journal_entry",
            "status",
        ]

    def create(self, validated_data):
        try:
            return accrue_gratuity(
                validated_data["employee"],
                as_of_date=validated_data["as_of_date"],
                provision_account=validated_data["provision_account"],
                expense_account=validated_data["expense_account"],
                basis_salary=validated_data.get("basis_salary"),
                user=self.context["request"].user,
            )
        except PayrollError as exc:
            logger.warning("Gratuity accrual rejected: %s", exc)
            raise serializers.ValidationError(
                {"non_field_errors": ["Could not accrue gratuity for this employee."]}
            ) from exc


class LeaveSerializer(serializers.ModelSerializer):
    """Create names employee/leave_type/accrued_amount/provision_account/
    expense_account/as_of_date (+ optional entitled_days/taken_days);
    `accrue_leave` books DR Leave Expense / CR Leave Provision."""

    employee_code = serializers.CharField(source="employee.code", read_only=True)
    employee_name = serializers.CharField(source="employee.name", read_only=True)

    class Meta:
        model = Leave
        fields = [
            "id",
            "entity",
            "employee",
            "employee_code",
            "employee_name",
            "leave_type",
            "entitled_days",
            "taken_days",
            "balance_days",
            "accrued_amount",
            "provision_account",
            "expense_account",
            "journal_entry",
            "as_of_date",
        ]
        read_only_fields = ["entity", "balance_days", "journal_entry"]

    def create(self, validated_data):
        try:
            return accrue_leave(
                validated_data["employee"],
                leave_type=validated_data["leave_type"],
                accrued_amount=validated_data["accrued_amount"],
                provision_account=validated_data["provision_account"],
                expense_account=validated_data["expense_account"],
                as_of_date=validated_data["as_of_date"],
                entitled_days=validated_data.get("entitled_days", 0),
                taken_days=validated_data.get("taken_days", 0),
                user=self.context["request"].user,
            )
        except PayrollError as exc:
            logger.warning("Leave accrual rejected: %s", exc)
            raise serializers.ValidationError(
                {"non_field_errors": ["Could not accrue leave salary for this employee."]}
            ) from exc
