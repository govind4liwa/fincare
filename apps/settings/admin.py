"""Admin for configuration models."""

from django.contrib import admin

from apps.settings.models import EntitySetting, FeatureFlag, NumberingSeries, VatConfig


@admin.register(EntitySetting)
class EntitySettingAdmin(admin.ModelAdmin):
    list_display = ("entity", "key")
    search_fields = ("key",)


@admin.register(NumberingSeries)
class NumberingSeriesAdmin(admin.ModelAdmin):
    list_display = ("entity", "doc_type", "format", "reset_policy")
    search_fields = ("doc_type",)


@admin.register(VatConfig)
class VatConfigAdmin(admin.ModelAdmin):
    list_display = ("entity", "key", "effective_from")
    list_filter = ("effective_from",)
    search_fields = ("key",)


@admin.register(FeatureFlag)
class FeatureFlagAdmin(admin.ModelAdmin):
    list_display = ("entity", "flag", "enabled")
    list_filter = ("enabled",)
    search_fields = ("flag",)
