"""DRF serializers for integrations: import profiles (column mappings),
import batches (run log), and the multipart upload payloads."""

from django.conf import settings

from rest_framework import serializers

from apps.integrations.models import ImportBatch, ImportKind, ImportProfile

# Canonical target fields each kind's column_map may bind, and the ones it must.
BANK_FIELDS = ("txn_date", "description", "reference", "deposit", "withdrawal", "running_balance")
PLATFORM_FIELDS = ("earning_date", "trip_ref", "driver_ref", "gross", "commission", "net")
REQUIRED_FIELDS = {
    ImportKind.BANK_STATEMENT: ("txn_date",),
    ImportKind.PLATFORM_EARNING: ("earning_date", "gross"),
}
ALLOWED_FIELDS = {
    ImportKind.BANK_STATEMENT: BANK_FIELDS,
    ImportKind.PLATFORM_EARNING: PLATFORM_FIELDS,
}

ALLOWED_EXTENSIONS = (".csv", ".txt", ".xlsx", ".xlsm")


class ImportProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportProfile
        fields = [
            "id",
            "entity",
            "kind",
            "name",
            "source_key",
            "column_map",
            "date_format",
            "skip_rows",
            "sheet",
            "is_active",
        ]

    def validate_column_map(self, value):
        if not isinstance(value, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in value.items()
        ):
            raise serializers.ValidationError(
                "column_map must map canonical field names to column headers (strings)."
            )
        return value

    def validate(self, attrs):
        kind = attrs.get("kind") or (self.instance.kind if self.instance else None)
        column_map = attrs.get("column_map")
        if column_map is None and self.instance:
            column_map = self.instance.column_map
        if kind and column_map is not None:
            allowed = set(ALLOWED_FIELDS[kind])
            unknown = sorted(set(column_map) - allowed)
            if unknown:
                raise serializers.ValidationError(
                    {
                        "column_map": (
                            f"Unknown field(s) {', '.join(unknown)} — "
                            f"allowed: {', '.join(ALLOWED_FIELDS[kind])}."
                        )
                    }
                )
            missing = [f for f in REQUIRED_FIELDS[kind] if not column_map.get(f)]
            if missing:
                raise serializers.ValidationError(
                    {"column_map": f"Required field(s) not mapped: {', '.join(missing)}."}
                )
        return attrs


class ImportBatchSerializer(serializers.ModelSerializer):
    profile_name = serializers.CharField(source="profile.name", read_only=True, default="")
    bank_account_code = serializers.CharField(
        source="bank_account.code", read_only=True, default=""
    )
    platform_name = serializers.CharField(source="platform.name", read_only=True, default="")
    imported_by_email = serializers.CharField(
        source="imported_by.email", read_only=True, default=""
    )

    class Meta:
        model = ImportBatch
        fields = [
            "id",
            "entity",
            "profile",
            "profile_name",
            "kind",
            "filename",
            "file_hash",
            "bank_account",
            "bank_account_code",
            "platform",
            "platform_name",
            "bank_statement",
            "row_count",
            "created_count",
            "skipped_count",
            "error_count",
            "status",
            "message",
            "imported_at",
            "imported_by_email",
        ]
        read_only_fields = fields


class _BaseUploadSerializer(serializers.Serializer):
    file = serializers.FileField(max_length=255)
    profile = serializers.UUIDField()

    def validate_file(self, value):
        name = (value.name or "").lower()
        if not name.endswith(ALLOWED_EXTENSIONS):
            raise serializers.ValidationError(
                f"Unsupported file type — use one of: {', '.join(ALLOWED_EXTENSIONS)}."
            )
        max_bytes = settings.INTEGRATIONS_MAX_UPLOAD_MB * 1024 * 1024
        if value.size > max_bytes:
            raise serializers.ValidationError(
                f"File is too large (limit {settings.INTEGRATIONS_MAX_UPLOAD_MB} MB)."
            )
        return value


class BankStatementUploadSerializer(_BaseUploadSerializer):
    bank_account = serializers.UUIDField()
    statement_no = serializers.CharField(
        max_length=64, required=False, allow_blank=True, default=""
    )


class PlatformEarningsUploadSerializer(_BaseUploadSerializer):
    platform = serializers.UUIDField()
