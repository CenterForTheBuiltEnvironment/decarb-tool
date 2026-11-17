"""Unit tests for utils/units.py conversions."""

import pytest

from utils.units import get_converter, get_inverse_converter

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "category",
    ["temperature", "power", "power_cooling", "capacity", "mass_g", "gwp", "energy", "area"],
)
@pytest.mark.parametrize("unit_mode", ["SI", "IP"])
def test_inverse_converter_round_trips(category, unit_mode):
    to_display = get_converter(category, unit_mode)
    to_base = get_inverse_converter(category, unit_mode)
    for value in (-12.5, 0.0, 1.0, 54_000.0):
        assert to_base(to_display(value)) == pytest.approx(value)


def test_inverse_temperature_is_affine():
    assert get_inverse_converter("temperature", "IP")(32.0) == pytest.approx(0.0)
    assert get_inverse_converter("temperature", "IP")(212.0) == pytest.approx(100.0)
