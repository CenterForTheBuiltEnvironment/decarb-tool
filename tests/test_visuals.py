"""Tests for result visualizations."""

from itertools import pairwise

import pandas as pd
import pytest

import utils.plotly_theme  # noqa: F401 - imports for side effect (sets default Plotly theme)
from src.visuals import DATE_TICKFORMATSTOPS, hover_date_format, plot_meter_timeseries


def source_energy_df():
    """Hourly source energy results, stamped with the simulated (E+) year."""
    index = pd.date_range("2001-01-01 01:00", periods=8760, freq="h", name="timestamp")
    return pd.DataFrame(
        {
            "eq_scen_id": "eq_scen_1",
            "em_scen_id": "em_scen_1",
            "elec_awhp_h_Wh": 100000.0,
            "elec_chiller_Wh": 50000.0,
            "gas_boiler_Wh": 25000.0,
        },
        index=index,
    )


def timeseries_figure(**kwargs):
    """Build the meter timeseries figure the results page renders."""
    return plot_meter_timeseries(source_energy_df(), "eq_scen_1", "em_scen_1", **kwargs)


class TestTimeseriesDateFormat:
    """The plotted year is a placeholder and must not reach the user."""

    def test_axis_tick_labels_omit_year(self):
        """Date ticks carry a format for every zoom level, none showing the year."""
        for stacked in (False, True):
            stops = timeseries_figure(freq="D", stacked=stacked).layout.xaxis.tickformatstops
            assert stops, "date axis falls back to Plotly's default ticks, which show the year"
            for stop in stops:
                assert "%Y" not in stop.value
                assert "%y" not in stop.value

    def test_axis_tick_stops_cover_all_zoom_levels(self):
        """Zoom ranges are contiguous, so no zoom level falls back to the default."""
        stops = timeseries_figure(freq="D").layout.xaxis.tickformatstops

        assert stops[0].dtickrange[0] is None, "no format below the finest tick spacing"
        assert stops[-1].dtickrange[1] is None, "no format above the coarsest tick spacing"
        for previous, current in pairwise(stops):
            assert previous.dtickrange[1] == current.dtickrange[0]

    def test_hover_omits_year(self):
        """Hover labels show month and day, not the placeholder year."""
        for stacked in (False, True):
            fig = timeseries_figure(freq="D", stacked=stacked)
            assert fig.data, "expected at least one meter trace"
            for trace in fig.data:
                assert "%Y" not in trace.hovertemplate
                assert "%y" not in trace.hovertemplate
                assert "Time: %{x|%b %d}" in trace.hovertemplate

    def test_hover_keeps_time_of_day_for_hourly_aggregation(self):
        """Hourly aggregation still needs the hour to be readable."""
        for trace in timeseries_figure(freq="h").data:
            assert "Time: %{x|%b %d, %H:%M}" in trace.hovertemplate
            assert "%Y" not in trace.hovertemplate

    def test_hover_drops_day_for_monthly_aggregation(self):
        """A month-end bin is labelled by its month."""
        for trace in timeseries_figure(freq="ME").data:
            assert "Time: %{x|%B}" in trace.hovertemplate

    def test_hover_date_format_per_frequency(self):
        """Every aggregation the user can pick maps to a year-free format."""
        assert hover_date_format("h") == "%b %d, %H:%M"
        assert hover_date_format("D") == "%b %d"
        assert hover_date_format("W") == "%b %d"
        assert hover_date_format("ME") == "%B"
        assert hover_date_format("unknown") == "%b %d"

    def test_axis_uses_shared_tick_formats(self):
        """The axis uses the module-level stops rather than a local copy."""
        stops = timeseries_figure(freq="D").layout.xaxis.tickformatstops

        assert [stop.value for stop in stops] == [s["value"] for s in DATE_TICKFORMATSTOPS]


class TestTimeseriesUnchangedBehaviour:
    """Formatting the dates must not move the plotted data."""

    def test_daily_totals_are_unchanged(self):
        """Daily sums still equal the raw hourly energy, in the auto-scaled unit."""
        fig = timeseries_figure(freq="D")

        chiller = next(trace for trace in fig.data if "Chiller" in trace.name)
        # first day starts at 01:00, so 23 hours; Wh scaled to MWh
        assert chiller.y[0] == pytest.approx(50000.0 * 23 / 1e6)
        assert chiller.y[1] == pytest.approx(50000.0 * 24 / 1e6)

    def test_x_values_keep_full_timestamps(self):
        """Only the labels lose the year - the underlying data is untouched."""
        fig = timeseries_figure(freq="D")

        assert pd.Timestamp(fig.data[0].x[0]) == pd.Timestamp("2001-01-01")

    def test_gas_can_still_be_excluded(self):
        """The gas toggle behaves as before."""
        fig = timeseries_figure(freq="D", include_gas=False)

        assert all("Gas" not in trace.name for trace in fig.data)
