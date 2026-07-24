"""DRF serializers for vouchers (writable nested lines)."""

from rest_framework import serializers

from apps.vouchers.models import Voucher, VoucherLine, VoucherStatus


class VoucherLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = VoucherLine
        fields = [
            "id",
            "line_no",
            "account",
            "description",
            "debit",
            "credit",
            "cost_center",
            "party_type",
            "party_id",
            "vehicle_id",
            "driver_id",
            "platform_id",
            "tax_code",
        ]


class VoucherSerializer(serializers.ModelSerializer):
    lines = VoucherLineSerializer(many=True)

    class Meta:
        model = Voucher
        fields = [
            "id",
            "entity",
            "branch",
            "voucher_type",
            "voucher_no",
            "voucher_date",
            "party_type",
            "party_id",
            "payment_mode",
            "bank_account",
            "cheque_no",
            "reference",
            "narration",
            "currency",
            "amount",
            "status",
            "journal_entry",
            "lines",
        ]
        read_only_fields = ["voucher_no", "amount", "status", "journal_entry"]

    def create(self, validated_data):
        lines = validated_data.pop("lines", [])
        voucher = Voucher.objects.create(**validated_data)
        for index, line in enumerate(lines, start=1):
            line.setdefault("line_no", index)
            VoucherLine.objects.create(voucher=voucher, **line)
        return voucher

    def update(self, instance, validated_data):
        if instance.status != VoucherStatus.DRAFT:
            raise serializers.ValidationError("Only draft vouchers can be edited.")
        lines = validated_data.pop("lines", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if lines is not None:
            instance.lines.all().delete()
            for index, line in enumerate(lines, start=1):
                line.setdefault("line_no", index)
                VoucherLine.objects.create(voucher=instance, **line)
        return instance
