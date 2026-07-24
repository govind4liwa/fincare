"""DRF serializers for AP suppliers, purchase bills, and debit notes."""

from rest_framework import serializers

from apps.ap.models import DebitNote, DebitNoteLine, PurchaseBill, PurchaseBillLine, Supplier


class SupplierSerializer(serializers.ModelSerializer):
    payable_account_code = serializers.CharField(source="payable_account.code", read_only=True)

    class Meta:
        model = Supplier
        fields = [
            "id",
            "entity",
            "code",
            "name",
            "trn",
            "payable_account",
            "payable_account_code",
            "currency",
            "credit_days",
            "email",
            "phone",
            "address",
            "opening_balance",
            "is_active",
        ]


class PurchaseBillLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseBillLine
        fields = [
            "id",
            "line_no",
            "account",
            "description",
            "quantity",
            "unit_price",
            "line_amount",
            "tax_code",
            "tax_rate",
            "tax_amount",
            "recoverable",
            "cost_center",
            "vehicle_id",
            "driver_id",
        ]
        # Amounts/rates are computed by the posting service, never trusted from input.
        read_only_fields = ["line_amount", "tax_rate", "tax_amount"]


class PurchaseBillSerializer(serializers.ModelSerializer):
    lines = PurchaseBillLineSerializer(many=True)
    supplier_code = serializers.CharField(source="supplier.code", read_only=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)

    class Meta:
        model = PurchaseBill
        fields = [
            "id",
            "entity",
            "branch",
            "supplier",
            "supplier_code",
            "supplier_name",
            "bill_no",
            "supplier_invoice_no",
            "bill_date",
            "due_date",
            "currency",
            "fx_rate",
            "subtotal",
            "tax_total",
            "total",
            "amount_allocated",
            "balance",
            "is_reverse_charge",
            "status",
            "journal_entry",
            "lines",
        ]
        # Everything monetary + the number/status is derived at post time.
        read_only_fields = [
            "bill_no",
            "subtotal",
            "tax_total",
            "total",
            "amount_allocated",
            "balance",
            "status",
            "journal_entry",
        ]

    def create(self, validated_data):
        lines = validated_data.pop("lines", [])
        bill = PurchaseBill.objects.create(**validated_data)
        for index, line in enumerate(lines, start=1):
            line.setdefault("line_no", index)
            PurchaseBillLine.objects.create(bill=bill, **line)
        return bill

    def update(self, instance, validated_data):
        from apps.ap.models import BillStatus

        if instance.status != BillStatus.DRAFT:
            raise serializers.ValidationError("Only draft bills can be edited.")
        lines = validated_data.pop("lines", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if lines is not None:
            instance.lines.all().delete()
            for index, line in enumerate(lines, start=1):
                line.setdefault("line_no", index)
                PurchaseBillLine.objects.create(bill=instance, **line)
        return instance


class DebitNoteLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = DebitNoteLine
        fields = [
            "id",
            "line_no",
            "account",
            "description",
            "line_amount",
            "tax_code",
            "tax_rate",
            "tax_amount",
        ]
        read_only_fields = ["tax_rate", "tax_amount"]


class DebitNoteSerializer(serializers.ModelSerializer):
    lines = DebitNoteLineSerializer(many=True)
    supplier_code = serializers.CharField(source="supplier.code", read_only=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)

    class Meta:
        model = DebitNote
        fields = [
            "id",
            "entity",
            "supplier",
            "supplier_code",
            "supplier_name",
            "debit_note_no",
            "debit_note_date",
            "original_bill",
            "reason",
            "subtotal",
            "tax_total",
            "total",
            "status",
            "journal_entry",
            "lines",
        ]
        read_only_fields = [
            "debit_note_no",
            "subtotal",
            "tax_total",
            "total",
            "status",
            "journal_entry",
        ]

    def create(self, validated_data):
        lines = validated_data.pop("lines", [])
        note = DebitNote.objects.create(**validated_data)
        for index, line in enumerate(lines, start=1):
            line.setdefault("line_no", index)
            DebitNoteLine.objects.create(debit_note=note, **line)
        return note
