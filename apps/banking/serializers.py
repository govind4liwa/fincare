"""DRF serializers for banking: bank accounts, statements, reconciliations."""

from rest_framework import serializers

from apps.accounts.models import Account
from apps.banking.models import (
    BankAccount,
    BankStatement,
    Reconciliation,
    ReconciliationItem,
    StatementLine,
)


class BankAccountSerializer(serializers.ModelSerializer):
    gl_account_code = serializers.CharField(source="gl_account.code", read_only=True)
    gl_account_name = serializers.CharField(source="gl_account.name", read_only=True)

    class Meta:
        model = BankAccount
        fields = [
            "id",
            "entity",
            "code",
            "name",
            "gl_account",
            "gl_account_code",
            "gl_account_name",
            "bank_name",
            "account_number",
            "iban",
            "swift",
            "branch_name",
            "currency",
            "is_active",
        ]

    def validate(self, attrs):
        gl = attrs.get("gl_account") or getattr(self.instance, "gl_account", None)
        entity = attrs.get("entity") or getattr(self.instance, "entity", None)
        if gl is not None:
            if gl.account_type != Account.AccountType.BANK:
                raise serializers.ValidationError(
                    {"gl_account": "Must be a bank-type GL account (account_type='bank')."}
                )
            if entity is not None and gl.entity_id != entity.id:
                raise serializers.ValidationError(
                    {"gl_account": "GL account belongs to a different entity."}
                )
        return attrs


class StatementLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = StatementLine
        fields = [
            "id",
            "line_no",
            "txn_date",
            "value_date",
            "description",
            "reference",
            "deposit",
            "withdrawal",
            "running_balance",
            "is_matched",
        ]
        read_only_fields = ["is_matched"]


class BankStatementSerializer(serializers.ModelSerializer):
    lines = StatementLineSerializer(many=True)
    bank_account_code = serializers.CharField(source="bank_account.code", read_only=True)

    class Meta:
        model = BankStatement
        fields = [
            "id",
            "entity",
            "bank_account",
            "bank_account_code",
            "statement_no",
            "statement_date",
            "period_start",
            "period_end",
            "opening_balance",
            "closing_balance",
            "status",
            "lines",
        ]
        read_only_fields = ["status"]

    def create(self, validated_data):
        lines = validated_data.pop("lines", [])
        statement = BankStatement.objects.create(**validated_data)
        for index, line in enumerate(lines, start=1):
            line.setdefault("line_no", index)
            StatementLine.objects.create(statement=statement, **line)
        return statement


class ReconciliationSerializer(serializers.ModelSerializer):
    bank_account_code = serializers.CharField(source="bank_account.code", read_only=True)

    class Meta:
        model = Reconciliation
        fields = [
            "id",
            "entity",
            "bank_account",
            "bank_account_code",
            "statement",
            "recon_date",
            "statement_balance",
            "gl_balance",
            "difference",
            "status",
        ]
        read_only_fields = ["statement_balance", "gl_balance", "difference", "status"]


class ReconciliationItemSerializer(serializers.ModelSerializer):
    statement_line = StatementLineSerializer(read_only=True)
    entry_no = serializers.CharField(source="journal_line.entry.entry_no", read_only=True)
    entry_date = serializers.DateField(source="journal_line.entry.entry_date", read_only=True)
    gl_debit = serializers.DecimalField(
        source="journal_line.debit", max_digits=18, decimal_places=2, read_only=True
    )
    gl_credit = serializers.DecimalField(
        source="journal_line.credit", max_digits=18, decimal_places=2, read_only=True
    )

    class Meta:
        model = ReconciliationItem
        fields = [
            "id",
            "match_type",
            "amount",
            "statement_line",
            "entry_no",
            "entry_date",
            "gl_debit",
            "gl_credit",
        ]
