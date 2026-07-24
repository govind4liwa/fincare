"""Tests for account-code composition and validation."""

import pytest

from apps.accounts.services import coding


def test_compose_account_code_ok():
    assert coding.compose_account_code("101", "400", "410", "001") == "101-400-410-001"


def test_compose_rejects_bad_segment():
    with pytest.raises(coding.CodeError):
        coding.compose_account_code("101", "40", "410", "001")  # main too short


def test_compose_group_code_main_and_sub():
    assert coding.compose_group_code("101", "100") == "101-100"
    assert coding.compose_group_code("101", "100", "110") == "101-100-110"


@pytest.mark.parametrize(
    "main,nature,side",
    [
        ("100", "asset", "D"),
        ("200", "liability", "C"),
        ("300", "equity", "C"),
        ("400", "income", "C"),
        ("500", "expense", "D"),
        ("600", "expense", "D"),
        ("700", "expense", "D"),
    ],
)
def test_nature_and_normal_balance(main, nature, side):
    assert coding.nature_for_main(main) == nature
    assert coding.normal_balance_for_main(main) == side


def test_normal_balance_override():
    # accumulated depreciation: asset band but credit balance
    assert coding.normal_balance_for_main("100", override="C") == "C"


def test_is_valid_code():
    assert coding.is_valid_code("101-400-410-001")
    assert not coding.is_valid_code("11-400-410-001")
    assert not coding.is_valid_code("xxx-400-410-001")
