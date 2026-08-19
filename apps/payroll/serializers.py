"""DRF serializers for payroll: salary components, employees, salary structure,
and the run -> payslip lifecycle."""

from rest_framework import serializers

from apps.payroll.models import Employee, EmployeeSalary, Payslip, PayslipLine, Run, SalaryComponent


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
