"""DRF serializers for AR customers, sales invoices, and credit notes."""

from rest_framework import serializers

from apps.ar.models import CreditNote, CreditNoteLine, Customer, SalesInvoice, SalesInvoiceLine


class CustomerSerializer(serializers.ModelSerializer):
    receivable_account_code = serializers.CharField(
        source="receivable_account.code", read_only=True
    )

    class Meta:
        model = Customer
        fields = [
            "id",
            "entity",
            "code",
            "name",
            "trn",
            "customer_type",
            "receivable_account",
            "receivable_account_code",
            "currency",
            "credit_limit",
            "credit_days",
            "email",
            "phone",
            "address",
            "emirate",
            "opening_balance",
            "is_active",
        ]


class SalesInvoiceLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalesInvoiceLine
        fields = [
            "id",
            "line_no",
            "revenue_account",
            "description",
            "quantity",
            "unit_price",
            "line_amount",
            "tax_code",
            "tax_rate",
            "tax_amount",
            "cost_center",
            "vehicle_id",
            "driver_id",
            "platform_id",
        ]
        # Amounts/rates are computed by the posting service, never trusted from input.
        read_only_fields = ["line_amount", "tax_rate", "tax_amount"]


class SalesInvoiceSerializer(serializers.ModelSerializer):
    lines = SalesInvoiceLineSerializer(many=True)
    customer_code = serializers.CharField(source="customer.code", read_only=True)
    customer_name = serializers.CharField(source="customer.name", read_only=True)

    class Meta:
        model = SalesInvoice
        fields = [
            "id",
            "entity",
            "branch",
            "customer",
            "customer_code",
            "customer_name",
            "invoice_no",
            "invoice_date",
            "due_date",
            "place_of_supply",
            "currency",
            "fx_rate",
            "subtotal",
            "tax_total",
            "total",
            "amount_allocated",
            "balance",
            "status",
            "journal_entry",
            "narration",
            "lines",
        ]
        # Everything monetary + the number/status is derived at post time.
        read_only_fields = [
            "invoice_no",
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
        invoice = SalesInvoice.objects.create(**validated_data)
        for index, line in enumerate(lines, start=1):
            line.setdefault("line_no", index)
            SalesInvoiceLine.objects.create(invoice=invoice, **line)
        return invoice

    def update(self, instance, validated_data):
        from apps.ar.models import InvoiceStatus

        if instance.status != InvoiceStatus.DRAFT:
            raise serializers.ValidationError("Only draft invoices can be edited.")
        lines = validated_data.pop("lines", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if lines is not None:
            instance.lines.all().delete()
            for index, line in enumerate(lines, start=1):
                line.setdefault("line_no", index)
                SalesInvoiceLine.objects.create(invoice=instance, **line)
        return instance


class CreditNoteLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditNoteLine
        fields = [
            "id",
            "line_no",
            "revenue_account",
            "description",
            "line_amount",
            "tax_code",
            "tax_rate",
            "tax_amount",
        ]
        read_only_fields = ["tax_rate", "tax_amount"]


class CreditNoteSerializer(serializers.ModelSerializer):
    lines = CreditNoteLineSerializer(many=True)
    customer_code = serializers.CharField(source="customer.code", read_only=True)
    customer_name = serializers.CharField(source="customer.name", read_only=True)

    class Meta:
        model = CreditNote
        fields = [
            "id",
            "entity",
            "customer",
            "customer_code",
            "customer_name",
            "credit_note_no",
            "credit_note_date",
            "original_invoice",
            "reason",
            "subtotal",
            "tax_total",
            "total",
            "status",
            "journal_entry",
            "lines",
        ]
        read_only_fields = [
            "credit_note_no",
            "subtotal",
            "tax_total",
            "total",
            "status",
            "journal_entry",
        ]

    def create(self, validated_data):
        lines = validated_data.pop("lines", [])
        note = CreditNote.objects.create(**validated_data)
        for index, line in enumerate(lines, start=1):
            line.setdefault("line_no", index)
            CreditNoteLine.objects.create(credit_note=note, **line)
        return note
