from decimal import Decimal

from src.formatting import format_brazilian_number, format_display_value, parse_brazilian_number


def test_parse_brazilian_number():
    assert parse_brazilian_number("2.200,50") == Decimal("2200.50")
    assert parse_brazilian_number("+12 mil") == Decimal("12000")


def test_format_brazilian_number():
    assert format_brazilian_number("12345", 0) == "12.345"
    assert format_brazilian_number("2200.5", 1) == "2.200,5"


def test_preserves_qualified_direct_values():
    assert format_display_value("+12 mil", 0) == "+12 mil"
    assert format_display_value("4.400+", 0) == "4.400+"
