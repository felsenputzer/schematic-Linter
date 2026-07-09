import pytest

from schematic_linter.parsers.value_parser import ValueKind, ValueParseError, parse_value


@pytest.mark.parametrize(
    "raw, kind, expected_magnitude, expected_unit",
    [
        ("10k", ValueKind.RESISTANCE, 10_000.0, "ohm"),
        ("4.7uF", ValueKind.CAPACITANCE, 4.7e-6, "F"),
        ("0R", ValueKind.RESISTANCE, 0.0, "ohm"),
        ("5.6K", ValueKind.RESISTANCE, 5600.0, "ohm"),
        ("1nF", ValueKind.CAPACITANCE, 1e-9, "F"),
        ("51uH", ValueKind.INDUCTANCE, 51e-6, "H"),
        ("20MHz", ValueKind.FREQUENCY, 20_000_000.0, "Hz"),
        ("200", ValueKind.RESISTANCE, 200.0, "ohm"),
        ("0", ValueKind.RESISTANCE, 0.0, "ohm"),
        ("3.3K", ValueKind.RESISTANCE, 3300.0, "ohm"),
        ("10pF", ValueKind.CAPACITANCE, 10e-12, "F"),
        ("470uH", ValueKind.INDUCTANCE, 470e-6, "H"),
        # European embedded-decimal shorthand
        ("4k7", ValueKind.RESISTANCE, 4700.0, "ohm"),
        ("2R2", ValueKind.RESISTANCE, 2.2, "ohm"),
        ("0R", ValueKind.RESISTANCE, 0.0, "ohm"),
    ],
)
def test_parse_value_common_shorthand(raw, kind, expected_magnitude, expected_unit):
    parsed = parse_value(raw, kind)
    assert parsed is not None
    assert parsed.magnitude == pytest.approx(expected_magnitude, rel=1e-9)
    assert parsed.unit == expected_unit


def test_parse_value_blank_returns_none():
    assert parse_value("", ValueKind.RESISTANCE) is None
    assert parse_value("   ", ValueKind.RESISTANCE) is None
    assert parse_value(None, ValueKind.RESISTANCE) is None


def test_parse_value_garbage_raises():
    with pytest.raises(ValueParseError):
        parse_value("BAT54SW", ValueKind.RESISTANCE)


def test_zero_ohm_is_zero():
    parsed = parse_value("0R", ValueKind.RESISTANCE)
    assert parsed.is_zero


def test_display_formatting_uses_appropriate_prefix():
    assert parse_value("5.6K", ValueKind.RESISTANCE).display == "5.6 kOhm"
    assert parse_value("20MHz", ValueKind.FREQUENCY).display == "20 MHz"
    assert parse_value("0", ValueKind.RESISTANCE).display == "0 Ohm"
