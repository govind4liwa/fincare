"""Account-code composition and validation (ADR-0004).

Pattern: EEE-MMM-SSS-CCC
  EEE = entity numeric_code (band digit + 2-digit sequence)
  MMM = Main account segment (first digit = nature)
  SSS = Sub-account segment
  CCC = Charge-code segment

Codes are generated only here — never typed by users or assembled elsewhere.
"""

import re

CODE_PATTERN = re.compile(r"^\d{3}-\d{3}-\d{3}-\d{3}$")
GROUP_PATTERN = re.compile(r"^\d{3}(-\d{3}){0,2}$")

# Main-account first digit -> (nature, normal balance side)
_NATURE_BY_FIRST_DIGIT = {
    "1": ("asset", "D"),
    "2": ("liability", "C"),
    "3": ("equity", "C"),
    "4": ("income", "C"),
    "5": ("expense", "D"),  # direct cost / COGS
    "6": ("expense", "D"),  # operating / overhead
    "7": ("expense", "D"),  # finance cost & tax
}


class CodeError(ValueError):
    """Raised when an account code or segment is malformed."""


def _check_segment(value, width, label):
    if not (isinstance(value, str) and value.isdigit() and len(value) == width):
        raise CodeError(f"{label} must be {width} digits, got {value!r}")


def compose_account_code(entity_code, main, sub, charge):
    """Build a full EEE-MMM-SSS-CCC account code."""
    _check_segment(entity_code, 3, "entity numeric_code")
    _check_segment(main, 3, "main segment")
    _check_segment(sub, 3, "sub segment")
    _check_segment(charge, 3, "charge segment")
    code = f"{entity_code}-{main}-{sub}-{charge}"
    if not CODE_PATTERN.match(code):
        raise CodeError(f"composed code is invalid: {code}")
    return code


def compose_group_code(entity_code, main, sub=None):
    """Build a group code: EEE-MMM (Main) or EEE-MMM-SSS (Sub)."""
    _check_segment(entity_code, 3, "entity numeric_code")
    _check_segment(main, 3, "main segment")
    if sub is None:
        return f"{entity_code}-{main}"
    _check_segment(sub, 3, "sub segment")
    return f"{entity_code}-{main}-{sub}"


def nature_for_main(main):
    """Return the accounting nature for a Main segment (by first digit)."""
    _check_segment(main, 3, "main segment")
    try:
        return _NATURE_BY_FIRST_DIGIT[main[0]][0]
    except KeyError as exc:
        raise CodeError(f"no nature mapping for main band {main[0]!r}") from exc


def normal_balance_for_main(main, override=None):
    """Return 'D' or 'C' for a Main segment, allowing a per-account override."""
    if override:
        return override
    _check_segment(main, 3, "main segment")
    try:
        return _NATURE_BY_FIRST_DIGIT[main[0]][1]
    except KeyError as exc:
        raise CodeError(f"no normal-balance mapping for main band {main[0]!r}") from exc


def is_valid_code(code):
    return bool(CODE_PATTERN.match(code or ""))
