"""Tests for load data validation and processing."""

import numpy as np
import pandas as pd
import pytest

from src.loads import STANDARD_COLUMNS, StandardLoad, ensure_datetime, get_load_data
from src.metadata import LoadData, Metadata


@pytest.mark.unit
class TestStandardLoad:
    """Tests for StandardLoad validation and processing."""

    def test_valid_load_creation(self, sample_load_df):
        """Test creation with valid data succeeds."""
        load = StandardLoad(sample_load_df)
        assert load.num_hours == len(sample_load_df)

    def test_missing_columns_raises_error(self):
        """Test that missing required columns raise ValueError."""
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2025-01-01", periods=100, freq="h"),
                "t_out_C": [20] * 100,
                # Missing heating_W and cooling_W
            }
        )
        with pytest.raises(ValueError, match="Missing required columns"):
            StandardLoad(df)

    def test_standard_columns_defined(self):
        """Test that STANDARD_COLUMNS constant is properly defined."""
        assert "t_out_C" in STANDARD_COLUMNS
        assert "heating_W" in STANDARD_COLUMNS
        assert "cooling_W" in STANDARD_COLUMNS

    def test_load_dataframe_accessible(self, standard_load):
        """Test that underlying DataFrame is accessible."""
        assert hasattr(standard_load, "df")
        assert isinstance(standard_load.df, pd.DataFrame)

    def test_load_has_timestamp_index(self, standard_load):
        """Test that load data has timestamp as index."""
        assert standard_load.df.index.name == "timestamp"

    def test_compute_load_stats(self, standard_load):
        """Test load statistics computation."""
        stats = standard_load.compute_load_stats()
        assert "hhw_max_load" in stats
        assert "chw_max_load" in stats
        assert stats["hhw_max_load"] >= 0
        assert stats["chw_max_load"] >= 0

    def test_leap_year_detection(self):
        """Test leap day detection for leap years."""
        # 2024 is a leap year (8784 hours)
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=8784, freq="h"),
                "t_out_C": [20] * 8784,
                "heating_W": [1000] * 8784,
                "cooling_W": [500] * 8784,
            }
        )
        load = StandardLoad(df)
        assert load.has_leap_day  # Use truthy check instead of 'is True'

    def test_non_leap_year_detection(self, sample_load_df):
        """Test leap day detection for non-leap years."""
        # 2025 is not a leap year (sample_load_df uses 2025)
        load = StandardLoad(sample_load_df)
        assert not load.has_leap_day  # Use falsy check instead of 'is False'


@pytest.mark.unit
class TestLoadDataValidation:
    """Tests for edge cases in load data validation."""

    def test_negative_heating_raises(self):
        """Test that negative heating load values are rejected."""
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2025-01-01", periods=100, freq="h"),
                "t_out_C": [20] * 100,
                "heating_W": [-1000] * 100,
                "cooling_W": [500] * 100,
            }
        )
        with pytest.raises(ValueError, match="negative"):
            StandardLoad(df)

    def test_negative_cooling_raises(self):
        """Test that negative cooling load values are rejected."""
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2025-01-01", periods=100, freq="h"),
                "t_out_C": [20] * 100,
                "heating_W": [1000] * 100,
                "cooling_W": [-500] * 100,
            }
        )
        with pytest.raises(ValueError, match="negative"):
            StandardLoad(df)

    def test_zero_loads_allowed(self):
        """Zero is the valid lower bound for load values."""
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2025-01-01", periods=100, freq="h"),
                "t_out_C": [20] * 100,
                "heating_W": [0] * 100,
                "cooling_W": [0] * 100,
            }
        )
        load = StandardLoad(df)
        assert load is not None


# ---------------------------------------------------------------------------
# ensure_datetime — three timestamp format paths
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEnsureDatetime:
    def test_timestamp_column_becomes_datetime(self):
        df = pd.DataFrame(
            {
                "timestamp": ["2025-01-01 00:00:00", "2025-01-01 01:00:00"],
                "t_out_C": [10.0, 11.0],
                "heating_W": [1000.0, 900.0],
                "cooling_W": [0.0, 0.0],
            }
        )
        ensure_datetime(df)
        assert pd.api.types.is_datetime64_any_dtype(df["timestamp"])

    def test_hour_of_year_column_converts_correctly(self):
        # HOY is 1-based: HOY 1 = Jan 1 00:00, HOY 2 = Jan 1 01:00
        df = pd.DataFrame(
            {
                "hour_of_year": [1, 2, 3],
                "t_out_C": [5.0, 6.0, 7.0],
                "heating_W": [1000.0, 900.0, 800.0],
                "cooling_W": [0.0, 0.0, 0.0],
            }
        )
        ensure_datetime(df)
        assert pd.api.types.is_datetime64_any_dtype(df["timestamp"])
        assert df["timestamp"].iloc[0] == pd.Timestamp("2025-01-01 00:00:00")
        assert df["timestamp"].iloc[1] == pd.Timestamp("2025-01-01 01:00:00")

    def test_month_day_hour_columns_convert_correctly(self):
        df = pd.DataFrame(
            {
                "month": [1, 1, 7],
                "day": [1, 1, 15],
                "hour": [0, 1, 0],
                "t_out_C": [5.0, 6.0, 25.0],
                "heating_W": [1000.0, 900.0, 0.0],
                "cooling_W": [0.0, 0.0, 500.0],
            }
        )
        ensure_datetime(df)
        assert pd.api.types.is_datetime64_any_dtype(df["timestamp"])
        assert df["timestamp"].iloc[0] == pd.Timestamp("2025-01-01 00:00:00")
        assert df["timestamp"].iloc[2] == pd.Timestamp("2025-07-15 00:00:00")

    def test_no_valid_time_column_raises(self):
        df = pd.DataFrame(
            {
                "t_out_C": [15.0],
                "heating_W": [1000.0],
                "cooling_W": [0.0],
            }
        )
        with pytest.raises(ValueError, match="No valid time column"):
            ensure_datetime(df)


# ---------------------------------------------------------------------------
# StandardLoad.get_data_summary — the function that powers the UI quality flags
# ---------------------------------------------------------------------------


def _make_annual_load(hours=8760, year=2025, nan_col=None, nan_count=0):
    """Helper: create a StandardLoad with optional NaN values in one column."""
    heating = [1000.0] * hours
    if nan_col == "heating_W":
        heating[:nan_count] = [np.nan] * nan_count

    cooling = [500.0] * hours
    if nan_col == "cooling_W":
        cooling[:nan_count] = [np.nan] * nan_count

    t_out = [15.0] * hours
    if nan_col == "t_out_C":
        t_out[:nan_count] = [np.nan] * nan_count

    return StandardLoad(
        pd.DataFrame(
            {
                "timestamp": pd.date_range(f"{year}-01-01", periods=hours, freq="h"),
                "t_out_C": t_out,
                "heating_W": heating,
                "cooling_W": cooling,
            }
        )
    )


@pytest.mark.unit
class TestGetDataSummary:
    def test_complete_data_flagged_as_complete(self):
        summary = _make_annual_load().get_data_summary()
        assert summary["is_complete"] is True
        assert summary["hours_complete"] is True
        assert summary["data_complete"] is True
        assert summary["missing_hours"] == 0
        assert summary["has_missing_values"] is False
        assert summary["total_missing_values"] == 0
        assert summary["num_hours"] == 8760

    def test_short_dataset_missing_hours_detected(self):
        summary = _make_annual_load(hours=8700).get_data_summary()
        assert summary["is_complete"] is False
        assert summary["hours_complete"] is False
        assert summary["missing_hours"] == 60

    def test_nan_values_detected_and_counted(self):
        summary = _make_annual_load(nan_col="heating_W", nan_count=5).get_data_summary()
        assert summary["is_complete"] is False
        assert summary["data_complete"] is False
        assert summary["has_missing_values"] is True
        assert summary["total_missing_values"] == 5
        assert summary["column_stats"]["heating_W"]["missing_count"] == 5
        assert summary["column_stats"]["cooling_W"]["missing_count"] == 0

    def test_per_column_completeness_percentage(self):
        load = _make_annual_load(hours=100, nan_col="t_out_C", nan_count=10)
        stats = load.get_data_summary()["column_stats"]["t_out_C"]
        assert stats["missing_count"] == 10
        assert stats["completeness_pct"] == pytest.approx(90.0)

    def test_leap_year_expects_8784_hours(self):
        summary = _make_annual_load(hours=8784, year=2024).get_data_summary()
        assert summary["has_leap_day"]  # np.bool_ from pandas .any()
        assert summary["expected_hours"] == 8784
        assert summary["is_complete"] is True
        assert summary["missing_hours"] == 0

    def test_multi_year_data_flagged(self):
        summary = _make_annual_load(hours=8760 * 2).get_data_summary()
        assert summary["spans_multiple_years"] is True


# ---------------------------------------------------------------------------
# StandardLoad.limit_to_one_year
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestLimitToOneYear:
    def test_single_year_data_unchanged(self):
        load = _make_annual_load(hours=8760)
        trimmed = load.limit_to_one_year()
        assert trimmed.num_hours == 8760

    def test_multi_year_data_trimmed_to_one_year(self):
        load = _make_annual_load(hours=8760 * 2)
        assert load.spans_multiple_years
        trimmed = load.limit_to_one_year()
        assert trimmed.num_hours == 8760
        assert not trimmed.spans_multiple_years

    def test_leap_year_result_retains_8784_hours(self):
        load = _make_annual_load(hours=8784, year=2024)
        trimmed = load.limit_to_one_year()
        assert trimmed.num_hours == 8784
        assert trimmed.has_leap_day

    def test_trimmed_data_starts_from_original_start_date(self):
        load = _make_annual_load(hours=8760 * 2)
        start_before = load.df.index.min()
        trimmed = load.limit_to_one_year()
        assert trimmed.df.index.min() == start_before


# ---------------------------------------------------------------------------
# get_load_data — the function the app calls to read from parquet
# ---------------------------------------------------------------------------


@pytest.mark.regression
class TestGetLoadData:
    def _meta(self, building_id, load_type, custom_path=None):
        return Metadata.create(
            building_id=building_id,
            load_data=LoadData(load_type=load_type),
            custom_load_path=custom_path,
        )

    def test_simulation_data_loads_for_valid_building(self):
        load = get_load_data(self._meta("5", "simulation"))
        assert isinstance(load, StandardLoad)
        assert load.num_hours == 8760

    def test_invalid_building_id_raises(self):
        with pytest.raises(ValueError, match="No simulation load found"):
            get_load_data(self._meta("99999", "simulation"))

    def test_missing_building_id_raises(self):
        with pytest.raises(ValueError, match="building_id required"):
            get_load_data(self._meta(None, "simulation"))

    def test_unsupported_load_type_raises(self):
        with pytest.raises(NotImplementedError, match="Unsupported load type"):
            get_load_data(self._meta("5", "unknown_type"))

    def test_custom_load_reads_from_parquet_file(self, tmp_path):
        hours = 8760
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2025-01-01", periods=hours, freq="h"),
                "t_out_C": np.full(hours, 15.0),
                "heating_W": np.full(hours, 1000.0),
                "cooling_W": np.full(hours, 500.0),
            }
        )
        parquet_path = tmp_path / "custom_load.parquet"
        df.to_parquet(parquet_path, index=False)

        load = get_load_data(self._meta(None, "custom", custom_path=str(parquet_path)))
        assert isinstance(load, StandardLoad)
        assert load.num_hours == hours
