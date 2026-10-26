"""Unit tests for figure builders in src/visuals.py."""

import pytest

import utils.plotly_theme  # noqa: F401 - registers the decarb-tool-theme template
from src.visuals import plot_performance_curves

pytestmark = pytest.mark.unit


class TestPlotPerformanceCurves:
    def test_awhp_has_cop_and_capacity_trace_per_supply_temperature(self, equipment_library):
        hp01 = equipment_library.get_equipment("hp01")
        fig = plot_performance_curves(hp01, "heating")
        n_lwt = len(hp01.performance_heating.leaving_supply_t)
        assert len(fig.data) == 2 * n_lwt
        assert {t.yaxis for t in fig.data} == {"y", "y2"}

    def test_hr_wwhp_plots_cop_against_capacity(self, equipment_library):
        hr01 = equipment_library.get_equipment("hr01")
        fig = plot_performance_curves(hr01, "heating")
        assert len(fig.data) == len(hr01.performance_heating.leaving_supply_t)
        assert "capacity" in fig.layout.xaxis.title.text.lower()

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
        assert fig.data[-2].y[0] == pytest.approx(sum(cops) / 2)

    def test_fixed_capacity_drawn_when_no_capacity_curves(self, equipment_library):
        fig = plot_performance_curves(equipment_library.get_equipment("hp02"), "heating")
        assert "Fixed capacity" in [t.name for t in fig.data]

    def test_out_of_range_points_use_open_markers(self, equipment_library):
        # hp01 at 52 °C is limited to -10 °C and above, its curve starts at -15 °C
        fig = plot_performance_curves(equipment_library.get_equipment("hp01"), "heating")
        trace_52 = next(t for t in fig.data if t.name.startswith("52"))
        assert trace_52.marker.symbol[0] == "circle-open"
        assert trace_52.marker.symbol[-1] == "circle"

    def test_equipment_without_curves_gives_empty_figure(self, equipment_library):
        fig = plot_performance_curves(equipment_library.get_equipment("bo01"), "heating")
        assert len(fig.data) == 0
        assert fig.layout.annotations
