"""Admin for the Reports module."""

from django.contrib import admin

from apps.reports.models import (
    ReportRun,
    ReportSchedule,
    StatementLine,
    StatementTemplate,
)


class StatementLineInline(admin.TabularInline):
    model = StatementLine
    extra = 0


@admin.register(StatementTemplate)
class StatementTemplateAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "entity", "is_active")
    list_filter = ("code", "is_active")
    inlines = [StatementLineInline]


@admin.register(ReportRun)
class ReportRunAdmin(admin.ModelAdmin):
    list_display = ("report_code", "entity_scope", "entity", "format", "status", "generated_at")
    list_filter = ("report_code", "status", "entity_scope")
    date_hierarchy = "created_at"
    readonly_fields = ("generated_at", "generated_by", "file_ref")


@admin.register(ReportSchedule)
class ReportScheduleAdmin(admin.ModelAdmin):
    list_display = ("name", "report_code", "entity_scope", "cron", "format", "is_active")
    list_filter = ("report_code", "is_active")
