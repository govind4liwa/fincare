"""Admin for the Chart of Accounts."""

from django.contrib import admin

from apps.accounts.models import Account, AccountGroup, TaxCode


@admin.register(AccountGroup)
class AccountGroupAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "level", "nature", "entity")
    list_filter = ("level", "nature", "entity")
    search_fields = ("code", "name", "segment")
    autocomplete_fields = ("entity", "parent")


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "account_type",
        "normal_balance",
        "is_control_account",
        "is_bank_account",
        "entity",
    )
    list_filter = ("account_type", "is_control_account", "is_bank_account", "is_active", "entity")
    search_fields = ("code", "name")
    autocomplete_fields = ("entity", "sub_group", "currency")


@admin.register(TaxCode)
class TaxCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "rate", "treatment", "direction", "entity")
    list_filter = ("treatment", "direction", "entity")
    search_fields = ("code", "name")
