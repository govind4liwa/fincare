"""Seed standard statement templates (TB/PNL/BS/CF) mapping COA bands to layout.

Idempotent. Group-default templates use ``entity=None`` (ADR-0004 bands make the
range mapping stable across entities). Presentation can later be edited per entity.
"""

from django.db import transaction

from apps.reports.models import StatementLine, StatementTemplate

# (line_no, label, line_type, main_from, main_to, sign, indent, is_bold)
PNL_LINES = [
    (10, "Revenue", "range", "400", "499", 1, 0, True),
    (20, "Direct Operating Cost", "range", "500", "599", -1, 0, False),
    (30, "Gross Profit", "subtotal", "", "", 1, 0, True),
    (40, "Overheads", "range", "600", "699", -1, 0, False),
    (50, "Finance & Tax", "range", "700", "799", -1, 0, False),
    (60, "Net Profit", "total", "", "", 1, 0, True),
]
BS_LINES = [
    (10, "Assets", "range", "100", "199", 1, 0, True),
    (20, "Liabilities", "range", "200", "299", 1, 0, True),
    (30, "Equity", "range", "300", "399", 1, 0, True),
    (40, "Liabilities + Equity + Result", "total", "", "", 1, 0, True),
]
CF_LINES = [
    (10, "Net Profit", "formula", "", "", 1, 0, True),
    (20, "Operating Activities", "header", "", "", 1, 0, True),
    (30, "Investing Activities", "header", "", "", 1, 0, True),
    (40, "Financing Activities", "header", "", "", 1, 0, True),
    (50, "Net Change in Cash", "total", "", "", 1, 0, True),
]
TB_LINES = [
    (10, "All Accounts", "range", "100", "799", 1, 0, False),
]

TEMPLATES = {
    "TB": ("Trial Balance", TB_LINES),
    "PNL": ("Profit & Loss", PNL_LINES),
    "BS": ("Balance Sheet", BS_LINES),
    "CF": ("Cash Flow (Indirect)", CF_LINES),
}


@transaction.atomic
def seed_statement_templates(entity=None):
    """Create the standard templates (idempotent). Returns the count created."""
    created = 0
    for code, (name, lines) in TEMPLATES.items():
        template, was_created = StatementTemplate.objects.get_or_create(
            entity=entity, code=code, defaults={"name": name}
        )
        created += int(was_created)
        if not was_created:
            continue
        for line_no, label, line_type, mf, mt, sign, indent, bold in lines:
            StatementLine.objects.create(
                template=template,
                line_no=line_no,
                label=label,
                line_type=line_type,
                main_from=mf,
                main_to=mt,
                sign=sign,
                indent=indent,
                is_bold=bold,
            )
    return created
