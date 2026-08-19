"""DRF serializers for fleet vehicles, vehicle loans, EMI schedules, vehicle
documents, and depreciation runs."""

from rest_framework import serializers

from apps.fleet.models import (
    DepreciationLine,
    DepreciationRun,
    LoanSchedule,
    Vehicle,
    VehicleDocument,
    VehicleLoan,
    VehicleLoanInstallment,
)


class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = [
            "id",
            "entity",
            "code",
            "plate_no",
            "plate_emirate",
            "make",
            "model",
            "model_year",
            "vin",
            "ownership",
            "acquisition_date",
            "acquisition_cost",
            "is_active",
        ]


class VehicleLoanSerializer(serializers.ModelSerializer):
    vehicle_code = serializers.CharField(source="vehicle.code", read_only=True)
    loan_account_code = serializers.CharField(source="loan_account.code", read_only=True)
    interest_account_code = serializers.CharField(source="interest_account.code", read_only=True)
    approved_schedule_version = serializers.SerializerMethodField()

    class Meta:
        model = VehicleLoan
        fields = [
            "id",
            "entity",
            "vehicle",
            "vehicle_code",
            "lender",
            "loan_account",
            "loan_account_code",
            "interest_account",
            "interest_account_code",
            "principal",
            "down_payment",
            "term_months",
            "emi_amount",
            "annual_interest_rate",
            "amortization_method",
            "quoted_flat_rate",
            "effective_annual_rate",
            "start_date",
            "first_payment_date",
            "is_active",
            "approved_schedule_version",
        ]

    def get_approved_schedule_version(self, obj):
        approved = next(
            (s for s in obj.schedules.all() if s.status == LoanSchedule.Status.APPROVED), None
        )
        return approved.version_no if approved else None

    def validate(self, attrs):
        entity = attrs.get("entity") or getattr(self.instance, "entity", None)
        vehicle = attrs.get("vehicle") or getattr(self.instance, "vehicle", None)
        if entity is not None and vehicle is not None and vehicle.entity_id != entity.id:
            raise serializers.ValidationError({"vehicle": "Vehicle belongs to a different entity."})
        return attrs


class LoanInstallmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleLoanInstallment
        fields = [
            "id",
            "installment_no",
            "due_date",
            "opening_balance",
            "principal_component",
            "interest_component",
            "total_amount",
            "closing_balance",
            "bank_account",
            "status",
            "journal_entry",
        ]
        # The schedule owns the numbers; only the paying bank account is set here.
        read_only_fields = [
            "installment_no",
            "due_date",
            "opening_balance",
            "principal_component",
            "interest_component",
            "total_amount",
            "closing_balance",
            "status",
            "journal_entry",
        ]


class LoanScheduleSerializer(serializers.ModelSerializer):
    installments = LoanInstallmentSerializer(many=True, read_only=True)
    posted_count = serializers.SerializerMethodField()

    class Meta:
        model = LoanSchedule
        fields = [
            "id",
            "loan",
            "version_no",
            "method",
            "opening_principal",
            "annual_interest_rate",
            "term_months",
            "first_payment_date",
            "total_principal",
            "total_interest",
            "total_payments",
            "status",
            "approved_at",
            "note",
            "posted_count",
            "installments",
        ]

    def get_posted_count(self, obj):
        return sum(1 for i in obj.installments.all() if i.status == "posted")


class VehicleDocumentSerializer(serializers.ModelSerializer):
    vehicle_code = serializers.CharField(source="vehicle.code", read_only=True)
    days_to_expiry = serializers.SerializerMethodField()

    class Meta:
        model = VehicleDocument
        fields = [
            "id",
            "vehicle",
            "vehicle_code",
            "doc_type",
            "doc_no",
            "issue_date",
            "expiry_date",
            "note",
            "days_to_expiry",
        ]

    def get_days_to_expiry(self, obj):
        return obj.days_to_expiry()


class DepreciationLineSerializer(serializers.ModelSerializer):
    vehicle_code = serializers.CharField(source="vehicle.code", read_only=True)

    class Meta:
        model = DepreciationLine
        fields = ["id", "vehicle", "vehicle_code", "amount"]


class DepreciationRunSerializer(serializers.ModelSerializer):
    """A draft run has no lines yet — `post_depreciation_run` builds them from
    active vehicles with depreciation configured, in the same call that posts."""

    lines = DepreciationLineSerializer(many=True, read_only=True)

    class Meta:
        model = DepreciationRun
        fields = [
            "id",
            "entity",
            "run_no",
            "run_date",
            "period_label",
            "total_amount",
            "status",
            "journal_entry",
            "lines",
        ]
        read_only_fields = ["run_no", "total_amount", "status", "journal_entry"]
