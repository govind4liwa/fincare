"""Admin registrations for core reference data."""

from django.contrib import admin

from apps.core.models import Attachment, Currency, ExchangeRate, NumberSequence


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "symbol", "decimal_places", "is_base", "is_active")
    list_filter = ("is_base", "is_active")
    search_fields = ("code", "name")


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ("from_currency", "to_currency", "rate", "rate_date", "source")
    list_filter = ("rate_date", "source")
    autocomplete_fields = ("from_currency", "to_currency")


@admin.register(NumberSequence)
class NumberSequenceAdmin(admin.ModelAdmin):
    list_display = ("code", "entity_id", "period_key", "next_value", "reset_policy")
    list_filter = ("reset_policy",)
    search_fields = ("code", "entity_id")


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ("original_name", "content_type", "object_id", "mime_type", "size_bytes")
    list_filter = ("content_type",)
    search_fields = ("original_name",)
