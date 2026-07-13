"""Config-driven payroll parameters (gratuity rule, SIF layout) from ``settings``.

UAE statutory figures are configuration, never hardcoded (CLAUDE.md §4.8). These
read per-entity ``EntitySetting`` rows by key, falling back to documented UAE Labour
Law defaults so a fresh entity works out of the box but can be overridden.
"""

from decimal import Decimal

from apps.settings.models import EntitySetting

# UAE Labour Law defaults (overridable via EntitySetting key="gratuity_rule").
GRATUITY_RULE_DEFAULT = {
    "days_per_year_first": 21,  # first 5 years: 21 days of basic per year
    "days_per_year_after": 30,  # beyond 5 years: 30 days per year
    "first_years": 5,
    "month_days": 30,  # day-rate = monthly basic / 30
    "cap_years": 2,  # total capped at 2 years' wage
}

# SIF (Salary Information File) layout (overridable via EntitySetting key="sif_layout").
SIF_LAYOUT_DEFAULT = {
    "version": "MOHRE-SIF-1",
    "delimiter": ",",
    "scr_tag": "SCR",  # Salary Control Record (header)
    "edr_tag": "EDR",  # Employee Detail Record
}


def _get(entity, key, default):
    row = EntitySetting.objects.filter(entity=entity, key=key).first()
    if row and isinstance(row.value, dict) and row.value:
        merged = dict(default)
        merged.update(row.value)
        return merged
    return dict(default)


def gratuity_rule(entity):
    return _get(entity, "gratuity_rule", GRATUITY_RULE_DEFAULT)


def sif_layout(entity):
    return _get(entity, "sif_layout", SIF_LAYOUT_DEFAULT)


def gratuity_eligible_days(service_years, rule):
    """Eligible EOSB days for a service period under the configured rule."""
    sy = Decimal(service_years)
    first = Decimal(rule["first_years"])
    if sy <= first:
        return sy * Decimal(rule["days_per_year_first"])
    return first * Decimal(rule["days_per_year_first"]) + (sy - first) * Decimal(
        rule["days_per_year_after"]
    )
