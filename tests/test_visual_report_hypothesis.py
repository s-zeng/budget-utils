from __future__ import annotations

from hypothesis import assume, given, strategies as st

from budget_utils import visual_report


@given(
    st.floats(
        min_value=-1_000_000,
        max_value=1_000_000,
        allow_nan=False,
        allow_infinity=False,
    ),
    st.booleans(),
)
def test_format_currency_zero_behavior(value: float, show_zero: bool) -> None:
    rounded = round(value, 2)
    formatted = visual_report._format_currency(value, show_zero=show_zero)
    if rounded == 0 and not show_zero:
        assert formatted == ""
        return
    assert formatted
    assert visual_report.Currency in formatted
    if rounded < 0:
        assert formatted.startswith("-")


@given(
    st.integers(min_value=0, max_value=255),
    st.integers(min_value=0, max_value=255),
    st.integers(min_value=0, max_value=255),
    st.floats(min_value=0, max_value=1, allow_nan=False, allow_infinity=False),
)
def test_darken_hex_preserves_format(
    red: int,
    green: int,
    blue: int,
    factor: float,
) -> None:
    color = f"#{red:02x}{green:02x}{blue:02x}"
    darkened = visual_report._darken_hex(color, factor=factor)
    assert darkened.startswith("#")
    assert len(darkened) == 7

    dark_red = int(darkened[1:3], 16)
    dark_green = int(darkened[3:5], 16)
    dark_blue = int(darkened[5:7], 16)
    assert dark_red <= red
    assert dark_green <= green
    assert dark_blue <= blue


@given(st.text(min_size=0, max_size=12))
def test_darken_hex_invalid_passthrough(value: str) -> None:
    is_hex = (
        value.startswith("#")
        and len(value) == 7
        and all(ch in "0123456789abcdefABCDEF" for ch in value[1:])
    )
    assume(not is_hex)
    assert visual_report._darken_hex(value) == value
