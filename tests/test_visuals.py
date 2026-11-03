"""Unit tests for figure builders in src/visuals.py."""

import math

import pytest

import utils.plotly_theme  # noqa: F401 - registers the decarb-tool-theme template
from src.visuals import plot_performance_curves

pytestmark = pytest.mark.unit


def _traces(fig, role):
    return [t for t in fig.data if t.meta == role]


class TestPlotPerformanceCurves:
    def test_awhp_has_cop_and_capacity_trace_per_supply_temperature(self, equipment_library):
        hp01 = equipment_library.get_equipment("hp01")
        fig = plot_performance_curves(hp01, "heating")
        n_lwt = len(hp01.performance_heating.leaving_supply_t)
        assert len(_traces(fig, "curve")) == 2 * n_lwt
        assert {t.yaxis for t in fig.data} == {"y", "y2"}

    def test_hr_wwhp_plots_cop_against_capacity(self, equipment_library):
        hr01 = equipment_library.get_equipment("hr01")
        fig = plot_performance_curves(hr01, "heating")
        assert len(_traces(fig, "curve")) == len(hr01.performance_heating.leaving_supply_t)
        assert not _traces(fig, "outside")  # HR WWHP curves have no outdoor air limits
        assert "capacity" in fig.layout.xaxis.title.text.lower()

    def test_awhp_panels_both_labelled_with_outdoor_temperature(self, equipment_library):
        fig = plot_performance_curves(equipment_library.get_equipment("hp01"), "heating")
        for axis in (fig.layout.xaxis, fig.layout.xaxis2):
            assert axis.title.text.startswith("Outdoor air temperature")
        assert fig.layout.xaxis.showticklabels
        assert fig.layout.yaxis.title.text == "COP"
        assert "capacity" in fig.layout.yaxis2.title.text.lower()

    def test_ip_units_on_temperature_axis(self, equipment_library):
        fig = plot_performance_curves(equipment_library.get_equipment("hp01"), "heating", "IP")
        assert "°F" in fig.layout.xaxis2.title.text
        assert fig.data[0].name.endswith("°F")

    def test_highlight_adds_interpolated_curve(self, equipment_library):
        hp01 = equipment_library.get_equipment("hp01")
        plain = plot_performance_curves(hp01, "heating")
        fig = plot_performance_curves(hp01, "heating", highlight_lwt_C=45.0)
        assert len(fig.data) == len(plain.data) + 2  # COP and capacity
        # halfway between the 38 and 52 °C curves at the first outdoor temperature
        cops = [hp01.performance_heating.leaving_supply_t[t].cop[0] for t in ("38", "52")]
        assert _traces(fig, "highlight")[0].y[0] == pytest.approx(sum(cops) / 2)

    def test_fixed_capacity_drawn_when_no_capacity_curves(self, equipment_library):
        fig = plot_performance_curves(equipment_library.get_equipment("hp02"), "heating")
        assert "Fixed capacity" in [t.name for t in fig.data]

    def test_part_outside_operating_limits_is_dashed(self, equipment_library):
        # hp01 at 52 °C is limited to -10 °C and above, its curve starts at -15 °C
        fig = plot_performance_curves(equipment_library.get_equipment("hp01"), "heating")
        solid = next(t for t in _traces(fig, "curve") if t.name.startswith("52"))
        dashed = next(t for t in _traces(fig, "outside") if t.name.startswith("52"))
        assert math.isnan(solid.y[0]) and not math.isnan(solid.y[-1])
        assert dashed.line.dash == "dash"
        assert dashed.marker.symbol[0] == "circle-open"
        # the 38 °C curve is within its limits everywhere
        assert not [t for t in _traces(fig, "outside") if t.name.startswith("38")]

    def test_compare_to_draws_original_curves_behind(self, equipment_library):
        from src.equipment import scale_performance

        hp01 = equipment_library.get_equipment("hp01")
        scaled = scale_performance(hp01, "heating", cop_factor=0.9)
        fig = plot_performance_curves(scaled, "heating", compare_to=hp01)
        original = _traces(fig, "original")
        assert len(original) == 2 * len(hp01.performance_heating.leaving_supply_t)
        assert fig.data[0].meta == "original"
        assert sum(t.showlegend is not False for t in original) == 1
        assert _traces(fig, "curve")[0].y[-1] == pytest.approx(0.9 * original[0].y[-1])

    def test_compare_to_ignores_equipment_of_another_kind(self, equipment_library):
        fig = plot_performance_curves(
            equipment_library.get_equipment("hp01"),
            "heating",
            compare_to=equipment_library.get_equipment("hr01"),
        )
        assert not _traces(fig, "original")

    def test_equipment_without_curves_gives_empty_figure(self, equipment_library):
        fig = plot_performance_curves(equipment_library.get_equipment("bo01"), "heating")
        assert len(fig.data) == 0
        assert fig.layout.annotations
