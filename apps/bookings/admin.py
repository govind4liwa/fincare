"""Admin for the Bookings module."""

from django.contrib import admin

from apps.bookings.models import Contract, Trip


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = (
        "trip_date",
        "trip_type",
        "platform",
        "vehicle",
        "driver",
        "fare",
        "commission",
        "net_revenue",
        "status",
    )
    list_filter = ("trip_type", "status", "entity", "platform")
    date_hierarchy = "trip_date"
    readonly_fields = ("net_revenue", "revenue_journal_entry")


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = (
        "contract_no",
        "customer",
        "billing_cycle",
        "monthly_amount",
        "start_date",
        "end_date",
        "status",
    )
    list_filter = ("status", "billing_cycle", "entity")
    search_fields = ("contract_no", "customer__code", "customer__name")
